import os
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

# Local-la run panna mattum .env load aagum
load_dotenv()

app = Flask(__name__)

# Vercel deployment-ku ithu romba mukkiyam
app_instance = app 

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Supabase connection
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_id(id_val):
    if id_val and str(id_val).isdigit():
        return int(id_val)
    return id_val

@app.route('/')
def index():
    return render_template('index.html')

# ---------------- PDF UPLOAD ---------------- #
@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files['file']
        doc_no = request.form.get('doc_no')
        doc_type = request.form.get('type') 

        if not doc_no:
            return jsonify({"error": "Document number missing"}), 400

        file_name = f"{doc_no}.pdf"
        folder = "quotes" if doc_type == 'quotation' else "invoices"
        storage_path = f"{folder}/{file_name}"
        file_bytes = file.read()

        res = supabase.storage.from_("quotation_pdfs").upload(
            path=storage_path, file=file_bytes, file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        public_url = supabase.storage.from_("quotation_pdfs").get_public_url(storage_path)

        if doc_type == 'quotation':
            supabase.table("quotations").update({"pdf_url": public_url}).eq("quotation_no", doc_no).execute()
        else:
            supabase.table("invoices").update({"pdf_url": public_url}).eq("invoice_no", doc_no).execute()

        return jsonify({"success": True, "url": public_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- CUSTOMER API ---------------- #
@app.route('/api/customers', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_customers():
    try:
        if request.method == 'GET':
            res = supabase.table('customers').select('*').order('id', desc=True).execute()
            return jsonify(res.data)

        elif request.method in ['POST', 'PUT']:
            data = request.json
            if not data.get('name') or not data.get('phone') or not data.get('address'):
                return jsonify({"error": "Name, Phone and Address are mandatory"}), 400

            phone = str(data.get('phone', ''))
            phone_digits = re.sub(r'\D', '', phone)
            data['phone'] = phone_digits

            for key in ['gst_number', 'email', 'address']:
                if key in data and (data[key] == "" or data[key] == "null"):
                    data[key] = None

            if request.method == 'POST':
                res = supabase.table('customers').insert(data).execute()
                return jsonify(res.data)
            else:
                cust_id = parse_id(data.pop('id', None))
                res = supabase.table('customers').update(data).eq('id', cust_id).execute()
                return jsonify(res.data)

        elif request.method == 'DELETE':
            cust_id = parse_id(request.args.get('id'))
            supabase.table('customers').delete().eq('id', cust_id).execute()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- PRODUCT API ---------------- #
@app.route('/api/products', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_products():
    try:
        if request.method == 'GET':
            res = supabase.table('products').select('*').order('id', desc=True).execute()
            return jsonify(res.data)

        elif request.method in ['POST', 'PUT']:
            data = request.json
            if not data.get('category') or not data.get('sub_category') or not data.get('rate'):
                return jsonify({"error": "Category, Sub Category and Rate are mandatory"}), 400

            data['rate'] = float(data['rate'])

            if request.method == 'POST':
                res = supabase.table('products').insert(data).execute()
                return jsonify(res.data)
            else:
                prod_id = parse_id(data.pop('id', None))
                res = supabase.table('products').update(data).eq('id', prod_id).execute()
                return jsonify(res.data)

        elif request.method == 'DELETE':
            prod_id = parse_id(request.args.get('id'))
            supabase.table('products').delete().eq('id', prod_id).execute()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- QUOTATION API ---------------- #
@app.route('/api/quotations', methods=['GET', 'POST', 'PUT'])
def manage_quotations():
    try:
        if request.method == 'GET':
            res = supabase.table('quotations').select('*, customers(*)').order('created_at', desc=True).execute()
            return jsonify(res.data)

        elif request.method == 'POST':
            data = request.json
            current_date = datetime.now()
            month_year = current_date.strftime("%m-%y") 
            prefix = f"SSV-{month_year}-Q"

            existing = supabase.table('quotations').select('quotation_no').ilike('quotation_no', f"{prefix}%").execute()
            existing_nos = [row['quotation_no'] for row in existing.data] if existing.data else []
            
            max_seq = 0
            for no in existing_nos:
                match = re.search(r'Q(\d+)$', no)
                if match:
                    max_seq = max(max_seq, int(match.group(1)))

            data['quotation_no'] = f"{prefix}{max_seq + 1:03d}"
            
            res = supabase.table('quotations').insert(data).execute()
            return jsonify(res.data)

        elif request.method == 'PUT':
            data = request.json
            quote_id = parse_id(data.pop('id', None))
            res = supabase.table('quotations').update(data).eq('id', quote_id).execute()
            return jsonify(res.data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- INVOICE API ---------------- #
@app.route('/api/invoices', methods=['GET', 'POST'])
def manage_invoices():
    try:
        if request.method == 'GET':
            res = supabase.table('invoices').select('*, customers(*)').order('created_at', desc=True).execute()
            return jsonify(res.data)

        elif request.method == 'POST':
            data = request.json
            quote_no = data.get('quotation_no')
            
            supabase.table('quotations').update({"status": "Closed"}).eq('quotation_no', quote_no).execute()

            inv_no = quote_no.replace('-Q', '-INV')
            data['invoice_no'] = inv_no
            
            check = supabase.table('invoices').select('id').eq('invoice_no', inv_no).execute()
            if check.data:
                 return jsonify({"error": "Invoice already generated for this quotation"}), 400

            res = supabase.table('invoices').insert(data).execute()
            return jsonify(res.data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Vercel context check
if __name__ == '__main__':
    app.run(debug=True, port=5000)