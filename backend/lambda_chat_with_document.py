import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DOCUMENTS_TABLE'])
bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('BEDROCK_REGION'))
MODEL_ID = os.environ.get('MODEL_ID', 'amazon.nova-lite-v1:0')

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    body = json.loads(event.get('body') or '{}')
    document_id = body.get('document_id')
    question = body.get('question')
    history = body.get('history', [])  # [{role: 'user'|'assistant', text: '...'}, ...]

    if not document_id or not question:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'document_id and question are required'})
        }

    result = table.get_item(Key={'document_id': document_id})
    item = result.get('Item')

    if not item or item.get('user_id') != user_sub:
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Not found or access denied'})
        }

    # Prefer the full extracted text; fall back to the summary/image
    # description if that's all we have (e.g. for images).
    context_text = item.get('extracted_text') or item.get('summary') or ''

    if not context_text.strip():
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'answer': "I don't have enough readable content from this document to answer questions about it."})
        }

    intro = (
        f"You are answering questions about a document called '{item.get('filename')}'. "
        f"Base your answers only on the following content. If the answer isn't in the "
        f"content, say so honestly rather than guessing.\n\n{context_text[:6000]}"
    )

    messages = [
        {'role': 'user', 'content': [{'text': intro}]},
        {'role': 'assistant', 'content': [{'text': 'Understood, I will answer using only that document.'}]}
    ]

    # Keep only the last few turns so the prompt doesn't grow unbounded
    for turn in history[-6:]:
        messages.append({'role': turn['role'], 'content': [{'text': turn['text']}]})

    messages.append({'role': 'user', 'content': [{'text': question}]})

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            'messages': messages,
            'inferenceConfig': {'maxTokens': 500}
        })
    )
    response_body = json.loads(response['body'].read())
    answer = response_body['output']['message']['content'][0]['text']

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'answer': answer})
    }
