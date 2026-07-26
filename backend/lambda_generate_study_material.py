import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('cloudvault-documents')
bedrock = boto3.client('bedrock-runtime', region_name='ap-southeast-2')

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    body = json.loads(event.get('body') or '{}')
    document_id = body.get('document_id')

    result = table.get_item(Key={'document_id': document_id})
    item = result.get('Item')

    if not item or item.get('user_id') != user_sub:
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Not found or access denied'})
        }

    context_text = item.get('extracted_text') or item.get('summary') or ''
    if not context_text.strip():
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': "There isn't enough readable content in this document to generate study material."})
        }

    prompt = f"""Based on the following study material, generate:
1. Exactly 5 multiple-choice questions, each with 4 options and one correct answer.
2. Exactly 5 flashcards (a term/question on the front, the answer/explanation on the back).

Respond with ONLY valid JSON, no markdown formatting, no code fences, in exactly this shape:
{{
  "mcqs": [
    {{"question": "...", "options": ["...", "...", "...", "..."], "correct_index": 0}}
  ],
  "flashcards": [
    {{"front": "...", "back": "..."}}
  ]
}}

Study material:
{context_text[:6000]}"""

    response = bedrock.invoke_model(
        modelId='amazon.nova-lite-v1:0',
        body=json.dumps({
            'messages': [{'role': 'user', 'content': [{'text': prompt}]}],
            'inferenceConfig': {'maxTokens': 1500}
        })
    )
    response_body = json.loads(response['body'].read())
    raw_text = response_body['output']['message']['content'][0]['text']

    # Models sometimes wrap JSON in ```json fences despite instructions -
    # strip those defensively before parsing.
    cleaned = raw_text.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.split('```')[1]
        if cleaned.startswith('json'):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    print(f"RAW MODEL OUTPUT: {cleaned[:2000]}")

    try:
        study_material = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Could not generate study material in the expected format. Try again.'})
        }

    table.update_item(
        Key={'document_id': document_id},
        UpdateExpression='SET study_material = :sm',
        ExpressionAttributeValues={':sm': json.dumps(study_material)}
    )

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(study_material)
    }
