
# updated_streamlit_app.py - Updated Streamlit App (Optional Monitoring)
import streamlit as st
import json
import pika
import os
from datetime import datetime

# RabbitMQ configuration
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "admin")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "admin123")
QUEUE_NAME = "email_summaries"

def get_queue_info():
    """Get queue information for monitoring"""
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        method = channel.queue_declare(queue=QUEUE_NAME, durable=True, passive=True)
        message_count = method.method.message_count
        
        connection.close()
        return message_count
    except Exception as e:
        st.error(f"Error connecting to RabbitMQ: {e}")
        return None

def main():
    st.title("📧 Email Auto-Response System Dashboard")
    
    st.markdown("""
    This dashboard monitors the email auto-response system that uses RabbitMQ for processing.
    
    **System Flow:**
    1. **Producer**: Fetches emails → Summarizes → Publishes to queue
    2. **Consumer**: Consumes summaries → Queries KB → Sends auto-response
    """)
    
    # Queue monitoring
    st.subheader("🔍 Queue Monitoring")
    
    if st.button("Refresh Queue Status"):
        message_count = get_queue_info()
        if message_count is not None:
            st.metric("Messages in Queue", message_count)
            if message_count > 0:
                st.info(f"There are {message_count} email(s) waiting to be processed.")
            else:
                st.success("All emails have been processed!")
        else:
            st.error("Unable to connect to RabbitMQ")
    
    # System status
    st.subheader("⚙️ System Components")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Producer (Email Fetcher)**")
        st.code("""
# Run the producer
python producer.py
        """)
        st.markdown("- Fetches new emails from IMAP")
        st.markdown("- Generates summaries using LLM")
        st.markdown("- Publishes to RabbitMQ queue")
    
    with col2:
        st.markdown("**Consumer (Auto-Responder)**")
        st.code("""
# Run the consumer
python consumer.py
        """)
        st.markdown("- Consumes email summaries from queue")
        st.markdown("- Queries knowledge base for solutions")
        st.markdown("- Sends automated responses")
    
    # Configuration
    st.subheader("🔧 Configuration")
    
    with st.expander("Environment Variables Required"):
        st.code("""
# Email Configuration
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# SMTP Configuration  
SENDER_EMAIL=support@yourcompany.com
SENDER_PASSWORD=smtp_app_password

# RabbitMQ Configuration (optional, has defaults)
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASSWORD=admin123
        """)
    
    # Instructions
    st.subheader("🚀 Quick Start")
    
    st.markdown("""
    1. **Start RabbitMQ**: `docker-compose up -d`
    2. **Set Environment Variables**: Configure your email credentials
    3. **Run Consumer**: `python consumer.py` (keeps running)
    4. **Run Producer**: `python producer.py` (processes emails once)
    5. **Schedule Producer**: Use cron job for automatic email processing
    """)
    
    st.info("💡 **Tip**: Run the consumer as a background service and schedule the producer to run every few minutes for continuous email processing.")

if __name__ == "__main__":
    main()

# ---
