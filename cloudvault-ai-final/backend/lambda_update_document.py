import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('cloudvault-documents')

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    body = json.loads(event.get('body') or '{}')
    document_id = body.get('document_id')

    if not document_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'document_id is required'})
        }

    result = table.get_item(Key={'document_id': document_id})
    item = result.get('Item')

    if not item or item.get('user_id') != user_sub:
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Not found or access denied'})
        }

    update_parts = []
    values = {}

    if 'folder' in body:
        folder = (body.get('folder') or 'Uncategorized').strip() or 'Uncategorized'
        update_parts.append('folder = :folder')
        values[':folder'] = folder

    if 'favorite' in body:
        update_parts.append('favorite = :favorite')
        values[':favorite'] = bool(body.get('favorite'))

    if not update_parts:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Nothing to update'})
        }

    table.update_item(
        Key={'document_id': document_id},
        UpdateExpression='SET ' + ', '.join(update_parts),
        ExpressionAttributeValues=values
    )

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'updated': True})
    }
