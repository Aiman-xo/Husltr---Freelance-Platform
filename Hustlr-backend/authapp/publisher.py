import pika
import json
import logging

logger =logging.getLogger(__name__)
def publish_user_details(user_id,role):
    
    try:

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='rabbitmq')
        )

        channel = connection.channel()

        # Declare the queue (Durable ensures messages aren't lost if RabbitMQ restarts)
        channel.queue_declare(queue='user_sync_que',durable=True)

        message ={
            'user_id':user_id,
            'role':role
        }

        channel.basic_publish(
            exchange='',
            routing_key='user_sync_que',
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent on disk
            )
        )
        connection.close()
        logger.info(f"Successfully synced User {user_id} ({role}) to RabbitMQ")
        
    except Exception as e:
        logger.error(f"Failed to publish to RabbitMQ: {str(e)}")
