import json
import os
import boto3
import uuid
import time

dynamodb = boto3.resource('dynamodb')
documents_table = dynamodb.Table(os.environ['DOCUMENTS_TABLE'])
shares_table = dynamodb.Table(os.environ['SHARES_TABLE'])

# Where the public share-viewing page lives (see share.html)
SITE_BASE = os.environ['SITE_URL'].rstrip('/')

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    body = json.loads(event.get('body') or '{}')
    document_id = body.get('document_id')
    expiry_hours = int(body.get('expiry_hours', 24))

    result = documents_table.get_item(Key={'document_id': document_id})
    item = result.get('Item')

    if not item or item.get('user_id') != user_sub:
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Not found or access denied'})
        }

    share_id = str(uuid.uuid4())
    expires_at = int(time.time()) + (expiry_hours * 3600)

    shares_table.put_item(
        Item={
            'share_id': share_id,
            'document_id': document_id,
            'owner_user_id': user_sub,
            'expires_at': expires_at
        }
    )

    share_url = f"{SITE_BASE}/share.html?id={share_id}"

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'shareUrl': share_url, 'expiresInHours': expiry_hours})
    }
