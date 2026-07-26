import json
import boto3

s3 = boto3.client('s3', region_name='ap-southeast-2')
BUCKET_NAME = 'cloudvault-ai-jai-2026'

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
