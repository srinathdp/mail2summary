
# consumer.py - KB Query Consumer and Auto-Response
import json
import logging
import pika
import smtplib
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from .kb_and_email import get_solution_from_kb

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RabbitMQ configuration
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "admin")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "admin123")
QUEUE_NAME = "email_summaries"

# SMTP configuration
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "your_support@gmail.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "your_app_password")

class EmailAutoResponseConsumer:
    def __init__(self):
        self.connection = None
        self.channel = None
        
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
            
            # Set QoS to process one message at a time
            self.channel.basic_qos(prefetch_count=1)
            
            logger.info("Connected to RabbitMQ successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False
    
    def extract_sender_email(self, from_field):
        """Extract email address from 'from' field"""
        try:
            if '<' in from_field and '>' in from_field:
                # Format: "Name <email@domain.com>"
                start = from_field.index('<') + 1
                end = from_field.index('>')
                return from_field[start:end].strip()
            else:
                # Assume it's just the email address
                return from_field.strip()
        except Exception as e:
            logger.error(f"Error extracting sender email: {e}")
            return from_field.strip()
    
    def send_auto_response(self, to_email, subject, query, solution):
        """Send automated response email"""
        try:
            # Create email content
            response_subject = f"Re: {subject}" if not subject.lower().startswith('re:') else subject
            
            email_content = f"""Hi there,

Thank you for contacting our support team. We've received your request and here's our response:

Your Query: {query}

Our Solution:
{solution}

If you need further assistance, please don't hesitate to reach out to us.

Best regards,
Support Team

---
This is an automated response. Please do not reply to this email.
"""
            
            # Create email message
            msg = MIMEMultipart()
            msg["From"] = SENDER_EMAIL
            msg["To"] = to_email
            msg["Subject"] = response_subject
            
            # Attach content
            msg.attach(MIMEText(email_content, "plain", "utf-8"))
            
            # Send email
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
            
            logger.info(f"Auto-response sent to: {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send auto-response to {to_email}: {e}")
            return False
    
    def process_email_message(self, ch, method, properties, body):
        """Process email message from queue"""
        try:
            # Decode message
            message_data = json.loads(body.decode('utf-8'))
            
            from_email = self.extract_sender_email(message_data.get('from', ''))
            subject = message_data.get('subject', 'No Subject')
            summary = message_data.get('summary', '')
            
            logger.info(f"Processing email from: {from_email}, Subject: {subject}")
            
            # Skip if it's a reply to avoid loops
            if message_data.get('is_reply', False):
                logger.info("Skipping reply email to avoid loops")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            # Query knowledge base for solution
            solution = get_solution_from_kb(summary)
            
            # Send auto-response
            if from_email and not from_email.lower().endswith(SENDER_EMAIL.split('@')[1]):
                success = self.send_auto_response(from_email, subject, summary, solution)
                
                if success:
                    logger.info(f"Successfully processed and responded to: {from_email}")
                else:
                    logger.error(f"Failed to send response to: {from_email}")
            else:
                logger.info("Skipping internal email or invalid sender")
            
            # Acknowledge message processing
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Start consuming messages from queue"""
        try:
            if not self.connect_rabbitmq():
                return False
            
            self.channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=self.process_email_message
            )
            
            logger.info("Starting to consume messages. Press CTRL+C to stop...")
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Consumer stopped by user")
            self.stop_consuming()
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            return False
    
    def stop_consuming(self):
        """Stop consuming messages"""
        try:
            if self.channel:
                self.channel.stop_consuming()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Consumer stopped and connection closed")
        except Exception as e:
            logger.error(f"Error stopping consumer: {e}")

def main():
    """Main function to run the consumer"""
    consumer = EmailAutoResponseConsumer()
    
    # Validate environment variables
    required_env_vars = ['SENDER_EMAIL', 'SENDER_PASSWORD']
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return
    
    try:
        consumer.start_consuming()
    except Exception as e:
        logger.error(f"Consumer failed: {e}")
    finally:
        consumer.stop_consuming()

if __name__ == "__main__":
    main()

# ---
