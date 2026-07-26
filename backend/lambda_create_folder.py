import json
import boto3

dynamodb = boto3.resource('dynamodb')
folders_table = dynamodb.Table('cloudvault-folders')

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    body = json.loads(event.get('body') or '{}')
    name = (body.get('name') or '').strip()

    if not name:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Folder name is required'})
        }

    # put_item with the same user_id + folder_name is naturally idempotent -
    # creating a folder that already exists just does nothing harmful.
    folders_table.put_item(Item={'user_id': user_sub, 'folder_name': name})

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'created': True, 'name': name})
    }
