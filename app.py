import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def index():
    return render_template('index.html')

# --- CUSTOMER ENDPOINTS ---
@app.route('/api/customers', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_customers():
    try:
        if request.method == 'GET':
            res = supabase.table('customers').select('*').order('id').execute()
            return jsonify(res.data)
        
        elif request.method == 'POST':
            data = request.json
            res = supabase.table('customers').insert(data).execute()
            return jsonify(res.data)
            
        elif request.method == 'PUT':
            data = request.json
            cust_id = data.pop('id')
            res = supabase.table('customers').update(data).eq('id', cust_id).execute()
            return jsonify(res.data)

        elif request.method == 'DELETE':
            cust_id = request.args.get('id')
            supabase.table('customers').delete().eq('id', cust_id).execute()
            return jsonify({"success": True})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- PRODUCT ENDPOINTS ---
@app.route('/api/products', methods=['GET', 'POST'])
def manage_products():
    try:
        if request.method == 'GET':
            res = supabase.table('products').select('*').order('id').execute()
            return jsonify(res.data)
        elif request.method == 'POST':
            data = request.json
            res = supabase.table('products').insert(data).execute()
            return jsonify(res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- QUOTATION ENDPOINTS ---
@app.route('/api/quotations', methods=['GET', 'POST'])
def manage_quotations():
    try:
        if request.method == 'GET':
            res = supabase.table('quotations').select('*, customers(name), products(name)').order('created_at', desc=True).execute()
            return jsonify(res.data)
            
        elif request.method == 'POST':
            data = request.json
            
            # Generate SSV-MM-XXX-Q Format
            current_month = datetime.now().strftime("%m")
            prefix = f"SSV-{current_month}-"
            
            existing = supabase.table('quotations').select('quotation_no').ilike('quotation_no', f"{prefix}%").execute()
            existing_nos = [row['quotation_no'] for row in existing.data] if existing.data else[]
            
            max_seq = 0
            for no in existing_nos:
                parts = no.split('-')
                if len(parts) >= 3 and parts[2].isdigit():
                    max_seq = max(max_seq, int(parts[2]))
                    
            data['quotation_no'] = f"{prefix}{max_seq + 1:03d}-Q"
            
            res = supabase.table('quotations').insert(data).execute()
            return jsonify(res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- INVOICE GENERATION & ENDPOINTS ---
@app.route('/api/generate_invoice', methods=['POST'])
def generate_invoice():
    try:
        quote_id = request.json.get('id')
        
        # 1. Fetch Quote
        quote_res = supabase.table('quotations').select('*').eq('id', quote_id).execute()
        if not quote_res.data:
            return jsonify({"error": "Quote not found"}), 404
        quote = quote_res.data[0]
        
        # 2. Map data to invoice
        invoice_no = quote['quotation_no'].replace('-Q', '-INV')
        invoice_data = {
            "invoice_no": invoice_no,
            "customer_id": quote['customer_id'],
            "product_id": quote['product_id'],
            "qty": quote['qty'],
            "rate": quote['rate'],
            "gst": quote['gst'],
            "cgst": quote['cgst'],
            "sgst": quote['sgst'],
            "discount": quote['discount'],
            "total": quote['total'],
            "quotation_date": quote.get('quotation_date'), # Carrying over the date
            "expiry_date": quote.get('expiry_date')
        }
        
        # 3. Insert Invoice & Delete Quotation
        supabase.table('invoices').insert(invoice_data).execute()
        supabase.table('quotations').delete().eq('id', quote_id).execute()
        
        return jsonify({"success": True, "invoice_no": invoice_no})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    try:
        res = supabase.table('invoices').select('*, customers(name), products(name)').order('created_at', desc=True).execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)