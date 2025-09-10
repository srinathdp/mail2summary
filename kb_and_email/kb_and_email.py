import chromadb
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sys

# Ensure UTF-8 encoding for console output to handle Unicode characters
sys.stdout.reconfigure(encoding='utf-8')

# ---------- Gmail / Outlook SMTP CONFIG ----------
SMTP_SERVER = "smtp.gmail.com"  # For Gmail. Use "smtp.office365.com" for Outlook
SMTP_PORT = 587
SENDER_EMAIL = "chandrakanthsrinath@gmail.com"  # Replace with your email
SENDER_PASSWORD = "tkop czsn ragw ytsf"  # Use App Password, not normal password
RECEIVER_EMAIL = "@gmail.com"  # Customer email mushamgayathridevi

# ---------- Function to generate plain text email ----------
def generate_email(customer_query, solution):
    return f"""Subject: Shopify Support

Hi there,

We received your request:
> {customer_query}

Hereâ€™s what we suggest:
{solution}

For more help, visit our Help Center: https://help.shopify.com

Thanks for reaching out to Shopify Support.
Weâ€™re here to help anytime!
"""

# ---------- Function to send email ----------
def send_email(subject, text_content, sender=SENDER_EMAIL, receiver=RECEIVER_EMAIL):
    try:
        # Create the email container
        msg = MIMEMultipart("alternative")
        msg["From"] = sender
        msg["To"] = receiver
        msg["Subject"] = subject

        # Attach plain text content
        msg.attach(MIMEText(text_content, "plain"))

        # Connect to SMTP server
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure connection
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(sender, receiver, msg.as_string())

        print("Email sent successfully!")

    except Exception as e:
        print(f"Error sending email: {str(e)}")
        # Optionally log to a file
        with open('error_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"Error sending email: {str(e)}\n")

# ---------- Function to query ChromaDB for solution ----------
def get_solution_from_kb(query_text, collection_name="support_kb1", persist_path="./chroma_db"):
    try:
        # Initialize ChromaDB client with persistence
        client = chromadb.PersistentClient(path=persist_path)
        
        # Access the collection
        collection = client.get_collection(collection_name)
        
        # Query the KB
        results = collection.query(
            query_texts=[query_text],
            n_results=1  # Get the top match
        )
        
        # Check if results are found
        if results["documents"] and results["metadatas"]:
            solution = results["metadatas"][0][0]["answer"]
            return solution
        else:
            return "Sorry, we couldn't find a solution in our knowledge base. Please contact support for further assistance."

    except ValueError as e:
        print(f"Error accessing collection '{collection_name}': {e}")
        return "Error: Knowledge base unavailable. Please try again later."
    except Exception as e:
        print(f"Error querying KB: {e}")
        return "Error: Unable to retrieve solution. Please contact support."

# ---------- Main execution ----------
if __name__ == "__main__":
    # Example customer query
    customer_query = "I am having delay with my order."
    
    # Query the KB for a solution
    solution = get_solution_from_kb(customer_query)
    
    # Generate email content
    subject = "Shopify Support - Your Query"
    email_content = generate_email(customer_query, solution)
    
    # Send the email
    send_email(subject, email_content)