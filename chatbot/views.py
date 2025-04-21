from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import os
import json
import pandas as pd
import sqlite3
import datetime
import google.generativeai as genai
from django.conf import settings
from django.contrib.auth import authenticate, login, get_user_model
from .models import SearchHistory, UploadedPDF
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

# For PDF thumbnail generation
from pdf2image import convert_from_path

# -------------------------------
# File paths and Gemini API Setup
# -------------------------------
EXCEL_PATH = os.path.join(settings.BASE_DIR, 'users.xlsx')
UPLOADS_METADATA_PATH = os.path.join(settings.BASE_DIR, 'uploads.xlsx')
PDF_UPLOAD_DIR = os.path.join(settings.BASE_DIR, 'pdf_uploads')
HISTORY_PATH = os.path.join(settings.BASE_DIR, 'history.xlsx')

# Database file paths
HISTORY_DB_PATH = os.path.join(settings.BASE_DIR, 'history.db')
UPLOADS_DB_PATH = os.path.join(settings.BASE_DIR, 'uploads.db')

GEMINI_API_KEY = "AIzaSyDDm4r9JfPcKL9nlje2Tu-65ghQNrpUNrE"
genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    generation_config=generation_config,
)


# -------------------------------
# Helper Functions for History & Uploads
# -------------------------------

def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(e)
    return conn

def create_history_table(conn):
    sql_create_history_table = """ CREATE TABLE IF NOT EXISTS history (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        email TEXT,
                                        query TEXT,
                                        response TEXT,
                                        score REAL,
                                        timestamp TEXT
                                    ); """
    try:
        c = conn.cursor()
        c.execute(sql_create_history_table)
    except sqlite3.Error as e:
        print(e)

def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(e)
    return conn

def create_uploads_table(conn):
    sql_create_uploads_table = """ CREATE TABLE IF NOT EXISTS uploads (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        subject TEXT,
                                        file_path TEXT,
                                        thumb_path TEXT
                                    ); """
    try:
        c = conn.cursor()
        c.execute(sql_create_uploads_table)
    except sqlite3.Error as e:
        print(e)

def ensure_history_db():
    conn = create_connection(HISTORY_DB_PATH)
    if conn is not None:
        create_history_table(conn)
        conn.close()

def ensure_uploads_db():
    conn = create_connection(UPLOADS_DB_PATH)
    if conn is not None:
        create_uploads_table(conn)
        conn.close()

def ensure_history_file():
    history_path = os.path.join(settings.BASE_DIR, 'history.xlsx')
    if not os.path.exists(history_path):
        df = pd.DataFrame(columns=['email', 'query', 'response', 'score', 'timestamp'])
        df.to_excel(history_path, index=False)
    return history_path

def save_history_to_excel(email, query, response, score):
    history_path = ensure_history_file()
    new_record = pd.DataFrame([[email, query, response, score, datetime.datetime.now()]],
                                columns=['email', 'query', 'response', 'score', 'timestamp'])
    try:
        existing_df = pd.read_excel(history_path)
        updated_df = pd.concat([existing_df, new_record], ignore_index=True)
    except Exception:
        updated_df = new_record
    updated_df.to_excel(history_path, index=False)

    # Save to SQLite
    ensure_history_db()
    conn = create_connection(HISTORY_DB_PATH)
    if conn is not None:
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO history (email, query, response, score, timestamp) VALUES (?, ?, ?, ?, ?)",
                        (email, query, response, score, datetime.datetime.now()))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error saving history to database: {e}")
        finally:
            conn.close()

def ensure_uploads_metadata_file():
    if not os.path.exists(UPLOADS_METADATA_PATH):
        df = pd.DataFrame(columns=['subject', 'file_path', 'thumb_path'])
        df.to_excel(UPLOADS_METADATA_PATH, index=False)

def ensure_pdf_upload_dir():
    if not os.path.exists(PDF_UPLOAD_DIR):
        os.makedirs(PDF_UPLOAD_DIR)

@require_POST
def save_uploads_metadata_to_db(request):
    print("save_uploads_metadata_to_db called")  # Debugging print.
    print(f"Request POST: {request.POST}")
    print(f"Request FILES: {request.FILES}")

    subject = request.POST.get('subject') #example.
    file_path = "path/to/file.txt" #example.
    thumb_path = "path/to/thumb.png" #example.



    print(f"Subject: {subject}, File Path: {file_path}, Thumb Path: {thumb_path}")
    print("Function called with:", subject, file_path, thumb_path)
    print("save_uploads_metadata_to_db called with:", subject, file_path, thumb_path)
    # Save to Excel
    ensure_uploads_metadata_file()
    uploads_excel_path = UPLOADS_METADATA_PATH
    new_record = pd.DataFrame([[subject, file_path, thumb_path]], columns=['subject', 'file_path', 'thumb_path'])
    try:
        existing_df = pd.read_excel(uploads_excel_path)
        updated_df = pd.concat([existing_df, new_record], ignore_index=True)
    except Exception as e:
        print(f"Excel save error: {e}") #Print excel error
        updated_df = new_record
    updated_df.to_excel(uploads_excel_path, index=False)
    print("Excel save complete") #Debugging print.

    # Save to SQLite
    ensure_uploads_db()
    conn = create_connection(UPLOADS_DB_PATH)
    if conn is not None:
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO uploads (subject, file_path, thumb_path) VALUES (?, ?, ?)",
                        (subject, file_path, thumb_path))
            conn.commit()
            print("Database save complete") #Debugging print.
        except sqlite3.Error as e:
            print(f"Error saving uploads to database: {e}")
        finally:
            conn.close()
# -------------------------------
# Chat Functions (Education-Only, Combined with History)
# -------------------------------
def start_chat_session():
    try:
        return model.start_chat(history=[])
    except Exception as e:
        print(f"Error starting chat session: {e}")
        return None

chat_session = start_chat_session()

def chat(request):
    response_text = None
    error = None

    if request.method == 'POST':
        try:
            if 'query' in request.POST:
                user_query = request.POST.get('query')
                prompt = f"Answer the following educational query in a clear detailed manner in plain text (no formatting, no bold): {user_query}"
                response_text = chat_session.send_message(prompt).text.strip()
                user_email = request.session.get('user_email', 'anonymous')
                save_history_to_excel(user_email, user_query, response_text, 0)
        except Exception as e:
            error = f"An unexpected error occurred: {e}"
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            print(response_text)
            return JsonResponse({'bot_response': response_text, 'error': error})
    
    user_email = request.session.get('user_email', 'anonymous')
    if user_email != 'anonymous':
        history_path = ensure_history_file()
        try:
            history_df = pd.read_excel(history_path)
            user_history = history_df[history_df['email'] == user_email]
            history_records = user_history.to_dict(orient="records")
        except Exception:
            history_records = []
    else:
        history_records = []

    return render(request, 'chat.html', {
        'response': response_text,
        'error': error,
        'history': history_records,
    })


# -------------------------------
# Link Fetching Function
# -------------------------------@csrf_exempt

@csrf_exempt
def fetch_links_view(request):
    """
    Django view for handling link fetching.
    Handles both GET (renders the HTML page) and POST (fetches links from Gemini API).
    """
    if request.method == "POST":
        query = request.POST.get("query", "").strip()
        if not query:
            return JsonResponse({"error": "Query is required."}, status=400)

        try:
            # Start a new chat session with the Gemini API
            chat_session = genai.GenerativeModel(
                model_name="gemini-2.0-flash-exp",
                generation_config={
                    "temperature": 1,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                    "response_mime_type": "text/plain",
                },
            ).start_chat(history=[])

            # Create a prompt for fetching links
            prompt = (
               "Provide 5 relevant links from the web related to the following query. "
                "Ensure the links are up-to-date and reliable sources"
                "Format:\n1. <Link>\n2. <Link>\n3. <Link>\n4. <Link>\n5. <Link>\n"
                "Do not provide any explanation or context, just the links."
                "Do not give the links in the brackets or square brackets the links format should strictly follow the example format"
                "example format:"
                "1.  https://www.pashtuns.com/"
                "2.  https://www.britannica.com/topic/Pashtun"
                "3.  https://idsa.in/idsacomments/Pashtuns_Afghanistan_GC_Singh_101011"
                "4.  https://www.worldhistory.org/Pashtuns/"
                "5.  https://minorityrights.org/minorities/pashtuns/"
            )

            # Fetch the response from the Gemini API
            response = chat_session.send_message(f"{prompt}\n{query}")
            print(response.text)
            return JsonResponse({"links": response.text.strip()})

        except Exception as e:
            print(f"Error fetching links: {e}")
            return JsonResponse({"error": "Error fetching links. Please try again later."}, status=500)

    elif request.method == "GET":
        # Render the HTML page for the GET request
        return render(request, "link.html")

    return JsonResponse({"error": "Invalid request method."}, status=405)

# -------------------------------
# PDF Functions (Updated)
# -------------------------------
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import os
import json
import datetime
import pandas as pd
from pdf2image import convert_from_path
from django.http import FileResponse, Http404 

# Make sure these helpers exist in your code:
# ensure_uploads_metadata_file() - ensures uploads.xlsx exists
# ensure_pdf_upload_dir() - ensures the pdf_uploads/ folder exists
# Also set these constants in your settings or at module level:
# UPLOADS_METADATA_PATH, PDF_UPLOAD_DIR

@csrf_exempt
def pdfs_view(request):
    """
    Django view for handling PDF uploads, listing them in a "card" UI,
    and providing + "delete" options. A thumbnail of the first
    page is generated via pdf2image.
    """
    # Ensure the metadata file and upload directory exist
    ensure_uploads_metadata_file()
    ensure_pdf_upload_dir()

    if request.method == 'POST':
        subject = request.POST.get('subject')
        pdf_file = request.FILES.get('pdf_file')

        if subject and pdf_file:
            try:
                # Validate file type
                if pdf_file.content_type != 'application/pdf':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Invalid file type. Please upload a PDF file.'
                    })
                
                # Save the PDF file to disk
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                filename = f"{timestamp}_{pdf_file.name}"
                file_path = os.path.join(PDF_UPLOAD_DIR, filename)
                with open(file_path, 'wb+') as destination:
                    for chunk in pdf_file.chunks():
                        destination.write(chunk)
                
                # Generate a thumbnail of the first page using pdf2image
                try:
                    images = convert_from_path(file_path, dpi=72, first_page=1, last_page=1)
                    thumb_filename = filename.replace('.pdf', '_thumb.png')
                    thumb_path = os.path.join(PDF_UPLOAD_DIR, thumb_filename)
                    images[0].save(thumb_path, 'PNG')
                except Exception as e:
                    print("Thumbnail generation failed:", e)
                    thumb_filename = ''  # fallback if needed

                # Save metadata in Excel
                df = pd.DataFrame([[subject, filename, thumb_filename]],
                                  columns=['subject', 'file_path', 'thumb_path'])
                try:
                    existing_df = pd.read_excel(UPLOADS_METADATA_PATH)
                    updated_df = pd.concat([existing_df, df], ignore_index=True)
                except FileNotFoundError:
                    updated_df = df
                updated_df.to_excel(UPLOADS_METADATA_PATH, index=False)
                # Call save_uploads_metadata_to_db to save to database
                db_data = request.POST.copy()
                db_data['file_path'] = filename
                db_data['thumb_path'] = thumb_filename

                save_uploads_metadata_to_db(request)


                return JsonResponse({'status': 'success'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
        else:
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'})

    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            filename = data.get('file_path')
            if filename:
                # Delete the PDF file from disk
                file_path = os.path.join(PDF_UPLOAD_DIR, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)

                # Also remove the thumbnail if it exists
                thumb_filename = filename.replace('.pdf', '_thumb.png')
                thumb_path = os.path.join(PDF_UPLOAD_DIR, thumb_filename)
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)

                # Remove record from Excel
                df = pd.read_excel(UPLOADS_METADATA_PATH)
                df = df[df['file_path'] != filename]
                df.to_excel(UPLOADS_METADATA_PATH, index=False)
                
                # Remove record from Excel
                df = pd.read_excel(UPLOADS_METADATA_PATH)
                df = df[df['file_path'] != filename]
                df.to_excel(UPLOADS_METADATA_PATH, index=False)


                return JsonResponse({'status': 'success'})
            return JsonResponse({'status': 'error', 'message': 'PDF file identifier not provided'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
        

    # GET request: List all uploaded PDFs
    try:
        df = pd.read_excel(UPLOADS_METADATA_PATH)
        pdfs = []
        for _, row in df.iterrows():
            pdf_filename = row['file_path']
            thumb_filename = row.get('thumb_path', '')
            # If the cell is NaN or empty, use a placeholder icon
            if pd.isna(thumb_filename):
                thumb_filename = ''

            pdfs.append({
                'subject': row['subject'],
                'file_path': pdf_filename,
                'filename': os.path.basename(pdf_filename),
                'pdf_url': f"/pdf_uploads/{pdf_filename}",
                'thumb_url': (f"/pdf_uploads/{thumb_filename}"
                              if thumb_filename
                              else "https://upload.wikimedia.org/wikipedia/commons/8/87/PDF_file_icon.svg")
            })
    except Exception as e:
        print("Error reading uploads metadata:", e)
        pdfs = []
    
    return render(request, 'videos.html', {'pdfs': pdfs})


def force_download(request, filename):
    file_path = os.path.join(PDF_UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True)
    else:
        raise Http404("File not found.")

# -------------------------------
# PDF Summary Function
# -------------------------------
@csrf_exempt
def pdf_summary_view(request):
    """
    Django view to handle PDF uploads and return a 200-word summary in plain text.
    """
    if request.method == "POST":
        if 'pdf_file' not in request.FILES:
            return JsonResponse({"error": "PDF file is required."}, status=400)
        pdf_file = request.FILES['pdf_file']
        temp_path = os.path.join(settings.BASE_DIR, "temp_pdf.pdf")
        try:
            with open(temp_path, "wb+") as f:
                for chunk in pdf_file.chunks():
                    f.write(chunk)
        except Exception as e:
            return JsonResponse({"error": f"Error saving PDF file: {e}"}, status=500)
        
        try:
            import PyPDF2
            with open(temp_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                extracted_text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text += page_text + "\n"
        except Exception as e:
            os.remove(temp_path)
            return JsonResponse({"error": f"Error reading PDF: {e}"}, status=500)
        
        os.remove(temp_path)
        
        prompt = f"Please summarize the following text in exactly 200 words in plain text (no formatting, no bold):\n{extracted_text}"
        try:
            summary = chat_session.send_message(prompt).text.strip()
        except Exception as e:
            return JsonResponse({"error": f"Error generating summary: {e}"}, status=500)
        
        return JsonResponse({"summary": summary})
    elif request.method == "GET":
        return render(request, "pdf_upload.html")
    return JsonResponse({"error": "Invalid request method."}, status=405)

# -------------------------------
# History Polling Endpoint
# -------------------------------
def get_history(request):
    user_email = request.session.get('user_email', 'anonymous')
    if user_email == 'anonymous':
        return JsonResponse({"history": [], "last_modified": 0})
    
    history_path = ensure_history_file()
    last_modified = os.path.getmtime(history_path)
    
    try:
        history_df = pd.read_excel(history_path)
        user_history = history_df[history_df['email'] == user_email]
        history_records = user_history.to_dict(orient="records")
    except FileNotFoundError:
        history_records = []
    
    return JsonResponse({"history": history_records, "last_modified": last_modified})

# -------------------------------
# Authentication and Other Views
# -------------------------------
User = get_user_model()
GLOBAL_ADMIN_LOGIN_STATUS = 0

def index(request):
    return render(request, 'index.html')

def login_view(request):
    global GLOBAL_ADMIN_LOGIN_STATUS
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = None
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            login(request, user)
            request.session['user_email'] = email
            if user.is_superuser:
                GLOBAL_ADMIN_LOGIN_STATUS = 1
                request.session['is_superuser'] = 1
            else:
                GLOBAL_ADMIN_LOGIN_STATUS = 0
                request.session['is_superuser'] = 0
            return redirect('home')
        
        # fallback: custom table authentication
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, password 
            FROM users 
            WHERE email = ? AND password = ?
        """, (email, password))
        user_custom = cursor.fetchone()
        conn.close()

        if user_custom:
            GLOBAL_ADMIN_LOGIN_STATUS = 0
            request.session['is_superuser'] = 0
            request.session['user_email'] = email
            return redirect('home')
        else:
            messages.error(request, "Invalid credentials")
            
    return render(request, 'login.html')

def register(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        address = request.POST.get('address')
        phone = request.POST.get('phone')

        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                username TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                address TEXT NOT NULL,
                phone TEXT NOT NULL
            )
        ''')
        cursor.execute("INSERT INTO users (full_name, username, email, password, address, phone) VALUES (?, ?, ?, ?, ?, ?)",
                       (full_name, username, email, password, address, phone))
        conn.commit()
        conn.close()

        df = pd.DataFrame([[full_name, username, email, password, address, phone]],
                          columns=['Full Name', 'Username', 'Email', 'Password', 'Address', 'Phone'])
        try:
            existing_df = pd.read_excel(EXCEL_PATH)
            df = pd.concat([existing_df, df], ignore_index=True)
        except FileNotFoundError:
            pass
        df.to_excel(EXCEL_PATH, index=False)

        messages.success(request, "Registration successful")
        return redirect('login')
    return render(request, 'register.html')

def home(request):
    return render(request, 'home.html')

def logout_view(request):
    global GLOBAL_ADMIN_LOGIN_STATUS
    GLOBAL_ADMIN_LOGIN_STATUS = 0  
    request.session.flush()
    return redirect('index')
