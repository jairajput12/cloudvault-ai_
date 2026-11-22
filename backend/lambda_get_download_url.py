import json
import os
import boto3
from botocore.config import Config

# Pre-signed URLs must use the bucket's regional address and Signature V4. The default
# client signs with V2 against s3.amazonaws.com, which answers a new regional bucket
# with a redirect that the browser's CORS check rejects.
s3 = boto3.client('s3', region_name=os.environ['AWS_REGION'],
                  config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}))
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DOCUMENTS_TABLE'])
BUCKET_NAME = os.environ['UPLOADS_BUCKET']

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    query_params = event.get('queryStringParameters') or {}
    document_id = query_params.get('document_id')

    result = table.get_item(Key={'document_id': document_id})
    item = result.get('Item')

    if not item or item.get('user_id') != user_sub:
        # Either the document doesn't exist, or it belongs to someone
        # else - return the same error either way, so we don't leak
        # which document IDs exist to a user who isn't allowed to see them.
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Not found or access denied'})
        }

    presigned_url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET_NAME, 'Key': item['s3_key']},
        ExpiresIn=300
    )

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'downloadUrl': presigned_url, 'filename': item['filename']})
    }
