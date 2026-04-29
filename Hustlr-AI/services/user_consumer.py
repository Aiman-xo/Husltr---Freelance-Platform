import pika
import json
import redis

redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)

def start_user_sync_consumer():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='user_sync_que',durable=True)

        def callback(ch,method,properties,body):
            data=json.loads(body)
            role=data.get('role')
            user_id=data.get('user_id')

            if user_id and role:
                redis_client.set(f"user_role:{user_id}", role)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='user_sync_que', on_message_callback=callback)
        channel.start_consuming()

    except Exception as e:
        print(e)