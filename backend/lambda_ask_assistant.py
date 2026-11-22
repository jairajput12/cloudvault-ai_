import json
import os
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DOCUMENTS_TABLE'])
bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('BEDROCK_REGION'))
MODEL_ID = os.environ.get('MODEL_ID', 'amazon.nova-lite-v1:0')

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    body = json.loads(event.get('body') or '{}')
    question = body.get('question')
    history = body.get('history', [])

    if not question:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'question is required'})
        }

    response = table.scan(FilterExpression=Attr('user_id').eq(user_sub))
    docs = response.get('Items', [])
    summarized_docs = [d for d in docs if d.get('summary')]

    if not summarized_docs:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'answer': "You don't have any summarized documents yet \u2014 upload something first, then ask me about it."})
        }

    # Cap how many documents we include so the prompt stays a reasonable size
    # as the library grows. Most recent 40 is plenty for a personal library.
    summarized_docs = sorted(summarized_docs, key=lambda d: d.get('upload_date', ''), reverse=True)[:40]

    library_context = "\n\n".join(
        f"[File: {d['filename']}]\n{d['summary'][:500]}"
        for d in summarized_docs
    )

    intro = (
        "You are an assistant with access to a user's document library. Below are "
        "summaries of their files. Answer the user's question using only this "
        "information. When your answer draws from a specific file, mention its "
        "filename. If nothing in the library is relevant, say so honestly rather "
        f"than guessing.\n\n{library_context[:7000]}"
    )

    messages = [
        {'role': 'user', 'content': [{'text': intro}]},
        {'role': 'assistant', 'content': [{'text': 'Understood, I will answer using only your library and cite filenames.'}]}
    ]

    for turn in history[-6:]:
        messages.append({'role': turn['role'], 'content': [{'text': turn['text']}]})

    messages.append({'role': 'user', 'content': [{'text': question}]})

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            'messages': messages,
            'inferenceConfig': {'maxTokens': 600}
        })
    )
    response_body = json.loads(response['body'].read())
    answer = response_body['output']['message']['content'][0]['text']

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'answer': answer})
    }
