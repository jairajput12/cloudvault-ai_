import json
import os
import boto3
import uuid
import base64
import urllib.parse
from datetime import datetime

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('BEDROCK_REGION'))
MODEL_ID = os.environ.get('MODEL_ID', 'amazon.nova-lite-v1:0')
table = dynamodb.Table(os.environ['DOCUMENTS_TABLE'])

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
UNSUPPORTED_IMAGE_EXTENSIONS = {'.heic', '.heif'}
TEXT_EXTENSIONS = {'.txt', '.md', '.csv', '.json'}

def get_extension(filename):
    if '.' not in filename:
        return ''
    return '.' + filename.rsplit('.', 1)[-1].lower()

def lambda_handler(event, context):
    record = event['Records'][0]
    bucket_name = record['s3']['bucket']['name']
    raw_key = urllib.parse.unquote_plus(record['s3']['object']['key'])
    file_size = record['s3']['object'].get('size', 0)

    if '/' in raw_key:
        user_id, display_filename = raw_key.split('/', 1)
    else:
        user_id, display_filename = 'unknown', raw_key

    document_id = str(uuid.uuid4())
    ext = get_extension(display_filename)

    if ext in IMAGE_EXTENSIONS:
        file_type = 'image'
    elif ext in UNSUPPORTED_IMAGE_EXTENSIONS:
        file_type = 'unsupported_image'
    elif ext in TEXT_EXTENSIONS:
        file_type = 'text'
    elif ext == '.pdf':
        file_type = 'pdf'
    else:
        file_type = 'other'

    table.put_item(
        Item={
            'document_id': document_id,
            'user_id': user_id,
            'filename': display_filename,
            's3_key': raw_key,
            's3_bucket': bucket_name,
            'upload_date': datetime.utcnow().isoformat(),
            'file_type': file_type,
            'folder': 'Uncategorized',
            'file_size': file_size,
            'favorite': False,
            'status': 'uploaded',
            'summary': '',
            'extracted_text': ''
        }
    )

    if file_type == 'unsupported_image':
        table.update_item(
            Key={'document_id': document_id},
            UpdateExpression='SET #s = :status, summary = :summary',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': 'summarized',
                ':summary': 'This is a HEIC/HEIF photo (common on iPhones). AI analysis needs a standard format \u2014 try converting to JPEG or PNG before uploading.'
            }
        )
        return {'statusCode': 200, 'body': json.dumps(f'Document {document_id} stored (unsupported image format)')}

    if file_type == 'other':
        return {'statusCode': 200, 'body': json.dumps(f'Document {document_id} stored (no AI processing for this file type)')}

    try:
        if file_type == 'image':
            summary_text = summarize_image(bucket_name, raw_key)
            extracted_text = ''
        elif file_type in ('text', 'pdf'):
            summary_text, extracted_text = summarize_document(bucket_name, raw_key, file_type)
        else:
            summary_text, extracted_text = None, ''

        if summary_text:
            table.update_item(
                Key={'document_id': document_id},
                UpdateExpression='SET #s = :status, summary = :summary, extracted_text = :extracted_text',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':status': 'summarized',
                    ':summary': summary_text,
                    ':extracted_text': extracted_text[:6000]  # bounded, chat will reuse this
                }
            )
    except Exception as e:
        print(f"AI processing failed: {str(e)}")
        # Record the failure so the page can say so, instead of showing "Processing" forever.
        table.update_item(
            Key={'document_id': document_id},
            UpdateExpression='SET #s = :status, ai_error = :message',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': 'failed',
                ':message': friendly_error(e)
            }
        )

    return {'statusCode': 200, 'body': json.dumps(f'Document {document_id} processed')}


def friendly_error(error):
    text = str(error)
    if 'ThrottlingException' in text or 'Too many tokens' in text:
        return "The AI service has reached its limit for this account, so there is no summary yet. Your file is saved."
    if 'ValidationException' in text and 'document' in text.lower():
        return "This PDF could not be read by the AI (it may be too large or protected), so there is no summary. Your file is saved."
    return "The AI could not process this file. Your file is saved."


def summarize_document(bucket_name, s3_key, file_type):
    if file_type == 'text':
        file_obj = s3.get_object(Bucket=bucket_name, Key=s3_key)
        text_content = file_obj['Body'].read().decode('utf-8', errors='ignore')
    else:
        text_content = extract_pdf_text(bucket_name, s3_key)

    if not text_content.strip():
        return "No readable text was found in this document.", ''

    trimmed = text_content[:8000]
    prompt = f"Summarize the following document in 3-4 sentences, then list 3 key points:\n\n{trimmed}"
    summary = call_nova_text(prompt)
    return summary, text_content


def extract_pdf_text(bucket_name, s3_key):
    # Nova reads the PDF directly (all pages, up to the Converse size limit), so no
    # separate OCR service is needed.
    pdf_bytes = s3.get_object(Bucket=bucket_name, Key=s3_key)['Body'].read()
    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{
            'role': 'user',
            'content': [
                {'document': {'format': 'pdf', 'name': 'document', 'source': {'bytes': pdf_bytes}}},
                {'text': 'Return the text of this document exactly as written, with no commentary. '
                         'If it has no readable text, return nothing.'}
            ]
        }],
        inferenceConfig={'maxTokens': 3000}
    )
    return response['output']['message']['content'][0]['text']


def summarize_image(bucket_name, s3_key):
    file_obj = s3.get_object(Bucket=bucket_name, Key=s3_key)
    image_bytes = file_obj['Body'].read()
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')

    ext = get_extension(s3_key).replace('.', '')
    fmt = 'jpeg' if ext in ('jpg', 'jpeg') else ext

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            'messages': [{
                'role': 'user',
                'content': [
                    {'image': {'format': fmt, 'source': {'bytes': image_b64}}},
                    {'text': 'Describe this image in 2-3 sentences, then list 3 tags for it (objects, scene, or theme).'}
                ]
            }],
            'inferenceConfig': {'maxTokens': 400}
        })
    )
    response_body = json.loads(response['body'].read())
    return response_body['output']['message']['content'][0]['text']


def call_nova_text(prompt):
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            'messages': [{'role': 'user', 'content': [{'text': prompt}]}],
            'inferenceConfig': {'maxTokens': 500}
        })
    )
    response_body = json.loads(response['body'].read())
    return response_body['output']['message']['content'][0]['text']
