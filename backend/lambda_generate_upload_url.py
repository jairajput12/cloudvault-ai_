import json
import os
import boto3
from botocore.config import Config

# Pre-signed URLs must use the bucket's regional address and Signature V4. The default
# client signs with V2 against s3.amazonaws.com, which answers a new regional bucket
# with a redirect that the browser's CORS check rejects.
s3 = boto3.client('s3', region_name=os.environ['AWS_REGION'],
                  config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}))
BUCKET_NAME = os.environ['UPLOADS_BUCKET']

def lambda_handler(event, context):
    # The authorizer already verified this token; 'sub' is the permanent,
    # unique user ID baked into it. Never trust a user_id sent by the client.
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    query_params = event.get('queryStringParameters') or {}
    filename = query_params.get('filename', 'unnamed-file')

    # Prefixing the S3 key with the user's ID keeps every user's files
    # physically separated in storage, not just hidden in the UI.
    s3_key = f"{user_sub}/{filename}"

    presigned_url = s3.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': BUCKET_NAME,
            'Key': s3_key,
            'ContentType': 'application/octet-stream'
        },
        ExpiresIn=300
    )

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'uploadUrl': presigned_url})
    }
