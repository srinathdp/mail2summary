# producer.py - Email Fetcher and Summary Producer
import json
import logging
import pika
import os
from .email_utils import fetch_emails_from_imap, decode_emails
from .LLM import init, summarize

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RabbitMQ configuration
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "admin")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "admin123")
QUEUE_NAME = "email_summaries"

class EmailSummaryProducer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.model = init()  # Initialize LLM models
        
    def connect_rabbitmq(self):
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare queue (idempotent)
            self.channel.queue_declare(queue=QUEUE_NAME, durable=True)
            logger.info("Connected to RabbitMQ successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False
    
    def publish_email_summary(self, email_data):
        """Publish email summary to RabbitMQ queue"""
        try:
            if not self.connection or self.connection.is_closed:
                if not self.connect_rabbitmq():
                    return False
                    
            message = json.dumps(email_data, ensure_ascii=False)
            
            self.channel.basic_publish(
                exchange='',
                routing_key=QUEUE_NAME,
                body=message.encode('utf-8'),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            logger.info(f"Published email summary for: {email_data.get('subject', 'No subject')}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False
    
    def process_emails(self, username, password, batch_size=5):
        """Fetch emails, summarize, and publish to queue"""
        try:
            # Fetch email IDs
            email_ids = fetch_emails_from_imap(username, password)
            if not email_ids:
                logger.info("No emails found")
                return
            
            # Process emails in batches
            for i in range(0, min(len(email_ids), batch_size)):
                email_messages = decode_emails(email_ids, i, i+1, username, password)
                
                for email_message in email_messages:
                    try:
                        content = email_message.get('content', '')
                        
                        # Generate summary if content is substantial
                        if len(content.strip()) >= 100:
                            summary_result = summarize(content, self.model[0])
                            summary_text = summary_result[0].get('summary_text', content) if summary_result else content
                        else:
                            summary_text = content
                        
                        # Prepare email data for queue
                        email_data = {
                            'message_id': email_message.get('Message ID', ''),
                            'from': email_message.get('from', ''),
                            'subject': email_message.get('subject', ''),
                            'original_content': content,
                            'summary': summary_text,
                            'is_reply': email_message.get('IsReply', False),
                            'in_reply_to': email_message.get('InReplyTo', ''),
                            'attachments': email_message.get('attachment', [])
                        }
                        
                        # Publish to queue
                        self.publish_email_summary(email_data)
                        
                    except Exception as e:
                        logger.error(f"Error processing individual email: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error processing emails: {e}")
    
    def close_connection(self):
        """Close RabbitMQ connection"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

def main():
    """Main function to run the producer"""
    # Email credentials (in production, use environment variables)
    EMAIL_USERNAME = os.environ.get("EMAIL_USERNAME", "your_email@gmail.com")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "your_app_password")
    
    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        logger.error("Email credentials not provided")
        return
    
    producer = EmailSummaryProducer()
    
    try:
        if producer.connect_rabbitmq():
            logger.info("Starting email processing...")
            producer.process_emails(EMAIL_USERNAME, EMAIL_PASSWORD)
            logger.info("Email processing completed")
        else:
            logger.error("Failed to connect to RabbitMQ")
    finally:
        producer.close_connection()

if __name__ == "__main__":
    main()

# ---
