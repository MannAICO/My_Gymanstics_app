import json
import os
import csv
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from werkzeug.utils import secure_filename
from email.message import EmailMessage
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import qrcode
import smtplib
from io import StringIO, BytesIO

# Flask app configuration
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Global paths for storing data
MEMBERS_FILE = "members.json"
ATTENDANCE_FILE = "attendance.json"
BILLING_FILE = "billing.json"
MEMBERS_CSV = os.path.join(os.path.dirname(__file__), "members.csv")
INVOICES_FILE = "invoices.json"  # File for saving invoices

# Ensure the CSV file exists (create with header if necessary)
if not os.path.exists(MEMBERS_CSV):
    with open(MEMBERS_CSV, 'w', newline='') as csvfile:
        fieldnames = ["member_id", "name", "age", "membership_type", "date_of_joining", "pricing_period", "pricing_amount", "email", "address"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

# --------------------------
# Data Model Classes
# --------------------------
class Member:
    def __init__(self, member_id, name, age, membership_type, date_of_joining, pricing_period, pricing_amount, email, address, next_renewal_date=None):
        self.member_id = member_id
        self.name = name
        self.age = age
        self.membership_type = membership_type
        self.date_of_joining = date_of_joining
        self.pricing_period = pricing_period
        self.pricing_amount = pricing_amount
        self.email = email
        self.address = address

    def to_dict(self):
        return {
            "member_id": self.member_id,
            "name": self.name,
            "age": self.age,
            "membership_type": self.membership_type,
            "date_of_joining": self.date_of_joining,
            "pricing_period": self.pricing_period,
            "pricing_amount": self.pricing_amount,
            "email": self.email,
            "address": self.address,
        }

class Attendance:
    def __init__(self):
        self.attendance = self.load_attendance()

    def load_attendance(self):
        if os.path.exists(ATTENDANCE_FILE):
            try:
                with open(ATTENDANCE_FILE, 'r') as file:
                    return json.load(file)
            except Exception as e:
                print("Error loading attendance:", e)
                return {}
        else:
            return {}

    def save_attendance(self):
        try:
            with open(ATTENDANCE_FILE, 'w') as file:
                json.dump(self.attendance, file)
        except Exception as e:
            print("Error saving attendance:", e)

    def mark_attendance(self, member_id, status):
        date_str = datetime.now().strftime("%Y-%m-%d")
        if date_str not in self.attendance:
            self.attendance[date_str] = {}
        self.attendance[date_str][member_id] = 'present' if status == '1' else 'absent'
        self.save_attendance()

class Billing:
    def __init__(self):
        self.billing_records = self.load_billing()

    def load_billing(self):
        if os.path.exists(BILLING_FILE):
            try:
                with open(BILLING_FILE, 'r') as file:
                    return json.load(file)
            except Exception as e:
                print("Error loading billing records:", e)
                return {}
        else:
            return {}

    def save_billing(self):
        try:
            with open(BILLING_FILE, 'w') as file:
                json.dump(self.billing_records, file)
        except Exception as e:
            print("Error saving billing records:", e)

    def generate_invoice(self, member_id, amount, description="", due_date=""):
        date_str = datetime.now().strftime("%Y-%m-%d")
        if not due_date:
            due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        invoice = {
            "invoice_id": None,
            "member_id": member_id,
            "amount": amount,
            "date_issued": date_str,
            "description": description,
            "due_date": due_date,
            "status": "pending",
        }
        return invoice

# --------------------------
# Main Gym Management System Class
# --------------------------
class GymManagementSystem:
    def __init__(self):
        self.members = self.load_members()
        self.attendance_obj = Attendance()
        self.attendance = self.attendance_obj.attendance
        self.billing = Billing()
        self.invoices = []
        self.load_invoices()  # Load persisted invoices
        self.next_invoice_id = self.get_next_invoice_id()

    def load_members(self):
        if os.path.exists(MEMBERS_FILE):
            try:
                with open(MEMBERS_FILE, 'r') as file:
                    members = json.load(file)
                    return members if isinstance(members, dict) else {}
            except Exception as e:
                print("Error loading members:", e)
                return {}
        return {}

    def save_members(self):
        try:
            with open(MEMBERS_FILE, 'w') as file:
                json.dump(self.members, file)
        except Exception as e:
            print("Error saving members:", e)

    def save_member_to_csv(self, member_data):
        try:
            with open(MEMBERS_CSV, 'a', newline='') as csvfile:
                fieldnames = ["member_id", "name", "age", "membership_type", "date_of_joining", "pricing_period", "pricing_amount", "email", "address"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerow(member_data)
        except Exception as e:
            print("Error saving member to CSV:", e)

    def get_next_member_id(self):
        if not self.members:
            return "1"
        max_id = max(int(member_id) for member_id in self.members.keys())
        return str(max_id + 1)

    def register_member(self, name, age, membership_type, date_of_joining, pricing_period, pricing_amount, email, address):
        self.members = self.load_members()
        member_id = self.get_next_member_id()
        member = Member(member_id, name, age, membership_type, date_of_joining, pricing_period, pricing_amount, email, address)
        self.members[member_id] = member.to_dict()
        self.save_members()
        self.save_member_to_csv(member.to_dict())
        return member_id

    def mark_attendance(self, member_id, status):
        if member_id not in self.members:
            return False
        self.attendance_obj.mark_attendance(member_id, status)
        self.attendance = self.attendance_obj.attendance
        return True

    def get_past_attendance(self, member_id):
        past_attendance = {}
        for date, records in self.attendance.items():
            if member_id in records:
                past_attendance[date] = records[member_id]
        return past_attendance

    def load_invoices(self):
        if os.path.exists(INVOICES_FILE):
            try:
                with open(INVOICES_FILE, 'r') as file:
                    self.invoices = json.load(file)
            except Exception as e:
                print("Error loading invoices:", e)
                self.invoices = []
        else:
            self.invoices = []

    def save_invoices(self):
        try:
            with open(INVOICES_FILE, 'w') as file:
                json.dump(self.invoices, file)
        except Exception as e:
            print("Error saving invoices:", e)

    def get_next_invoice_id(self):
        if not self.invoices:
            return 1
        max_id = max(inv["invoice_id"] for inv in self.invoices)
        return max_id + 1

    # Updated generate_invoice method with payment_method field
    def generate_invoice(self, member_id, amount, description="", due_date="", payment_method=""):
        if member_id in self.members:
            invoice = self.billing.generate_invoice(member_id, amount, description, due_date)
            invoice["invoice_id"] = self.next_invoice_id
            invoice["status"] = "pending"
            invoice["payment_method"] = payment_method
            self.next_invoice_id += 1
            self.invoices.append(invoice)
            self.save_invoices()
            return True
        return False

    def get_all_members(self):
        return list(self.members.values())

    def get_member_invoices(self, member_id):
        return [invoice for invoice in self.invoices if invoice["member_id"] == member_id]

# --------------------------
# Helper Functions for PDF and Email
# --------------------------
def generate_invoice_pdf(member_id, invoice_id, amount, description, due_date, filename, payment_method=""):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Define Colors and Fonts
    primary_color = colors.HexColor("#1E3A8A")    # Navy Blue
    success_color = colors.HexColor("#16A34A")      # Green
    warning_color = colors.HexColor("#E11D48")       # Red (for Check payment)
    secondary_color = warning_color if payment_method.lower() == "check" else success_color
    background_color = colors.HexColor("#F3F4F6")     # Light Gray
    footer_color = colors.HexColor("#6B7280")         # Gray

    # Margins
    left_margin = 50
    right_margin = 50
    top_margin = 50
    bottom_margin = 50

    # Draw Background
    c.setFillColor(background_color)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # HEADER SECTION
    header_height = 100
    c.setFillColor(primary_color)
    c.rect(left_margin, height - top_margin - header_height, width - left_margin - right_margin, header_height, fill=1, stroke=0)

    # Invoice Title on Header
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(colors.white)
    c.drawRightString(width - right_margin - 10, height - top_margin - 40, "INVOICE")

    # Separator Under Header
    c.setStrokeColor(primary_color)
    c.setLineWidth(2)
    c.line(left_margin, height - top_margin - header_height - 10, width - right_margin, height - top_margin - header_height - 10)

    # Invoice Details Section
    details_top = height - top_margin - header_height - 30
    c.setFillColor(colors.white)
    c.rect(left_margin, details_top - 60, width - left_margin - right_margin, 60, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(primary_color)
    c.drawString(left_margin + 15, details_top - 20, f"Invoice ID: {invoice_id}")
    c.drawRightString(width - right_margin - 15, details_top - 20, f"Due Date: {due_date}")

    # Billing Information Section ("Bill To")
    billing_top = details_top - 80
    c.setFillColor(primary_color)
    c.rect(left_margin, billing_top - 70, width - left_margin - right_margin, 70, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.white)
    c.drawString(left_margin + 15, billing_top - 30, "Bill To:")
    c.setFont("Helvetica", 12)
    c.drawString(left_margin + 15, billing_top - 50, f"Member ID: {member_id}")

    # Invoice Breakdown Section
    breakdown_top = billing_top - 90
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(primary_color)
    c.drawString(left_margin + 15, breakdown_top, "Invoice Breakdown:")
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.black)
    c.drawString(left_margin + 15, breakdown_top - 20, f"Description: {description}")
    c.drawString(left_margin + 15, breakdown_top - 40, f"Total Amount: INR {amount}")

    # Payment Method Display
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(primary_color)
    c.drawString(left_margin + 15, breakdown_top - 60, f"Payment Method: {payment_method}")

    # Payment Status Section (Pending)
    status_top = breakdown_top - 90
    c.setFillColor(warning_color)
    c.rect(left_margin, status_top - 40, width - left_margin - right_margin, 40, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.white)
    c.drawString(left_margin + 15, status_top - 20, "Payment Status: Pending")

    # QR Code for Payment (Optional)
    payment_url = f"https://yourpaymentgateway.com/pay?invoice={invoice_id}&amount={amount}"
    qr = qrcode.make(payment_url)
    qr_bytes = BytesIO()
    qr.save(qr_bytes, format='PNG')
    qr_bytes.seek(0)
    try:
        qr_image = ImageReader(qr_bytes)
        qr_size = 80
        c.drawImage(qr_image, width - right_margin - qr_size, status_top - 35, width=qr_size, height=qr_size)
        c.setFont("Helvetica", 10)
        c.setFillColor(primary_color)
        c.drawCentredString(width - right_margin - qr_size/2, status_top - 45, "Scan to Pay")
    except Exception as e:
        c.drawString(width - right_margin - 100, status_top - 20, "[QR Code Unavailable]")

    # Footer Section with Thank You Note
    c.setFont("Helvetica-Oblique", 10)
    c.setFillColor(footer_color)
    footer_text = "Thank you for your business! Please make the payment before the due date to avoid penalties."
    c.drawCentredString(width/2, bottom_margin - 10, footer_text)

    c.save()
    print(f"PDF Invoice saved as {filename}")

def send_email_with_invoice(receiver_email, subject, body, pdf_filename):
    sender_email = "mannmakwana2002@gmail.com"  
    sender_password = "igbe tayd tgrb vymq"  # Replace with your app-specific password

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg.set_content(body, charset="utf-8")
    
    if pdf_filename is not None:
        try:
            with open(pdf_filename, "rb") as pdf_file:
                pdf_data = pdf_file.read()
                msg.add_attachment(pdf_data, maintype="application", subtype="pdf", filename=os.path.basename(pdf_filename))
        except Exception as e:
            print("Error reading PDF file:", e)
            return False

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print("Email sent successfully!")
        return True
    except Exception as e:
        print("Error sending email:", e)
        return False

# --------------------------
# Initialize Gym Management System
# --------------------------
gym_system = GymManagementSystem()

# --------------------------
# Flask Routes
# --------------------------
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register_member():
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        date_of_joining = request.form['date_of_joining']
        membership_type = request.form['membership_type']
        pricing_period = request.form['pricing_period']
        pricing_amount = request.form['pricing_amount']
        email = request.form['email']              # New field
        address = request.form['address']          # New field

        gym_system.register_member(name, age, membership_type, date_of_joining, pricing_period, pricing_amount, email, address)
        flash('Member registered successfully!', 'success')
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/attendance', methods=['GET', 'POST'])
def mark_attendance():
    if request.method == 'POST':
        member_id = request.form.get('member_id')
        status = request.form.get('status')
        if member_id and status in ['0', '1']:
            if gym_system.mark_attendance(member_id, status):
                flash(f'✅ Attendance marked for Member ID: {member_id}', 'attendance')
            else:
                flash('❌ No member found with that ID', 'attendance')
        else:
            flash('❌ Invalid data. Please try again.', 'attendance')
        return redirect(url_for('mark_attendance'))
    
    return render_template('attendance.html')

@app.route('/attendance_report')
def attendance_report():
    attendance_data = gym_system.attendance
    return render_template('attendance_report.html', attendance_data=attendance_data)

@app.route('/view_past_attendance', methods=['GET', 'POST'])
def view_past_attendance_form():
    if request.method == 'POST':
        member_id = request.form['member_id']
        return redirect(url_for('view_past_attendance_by_id', member_id=member_id))
    return render_template('view_past_attendance.html')

@app.route('/view_past_attendance/<member_id>')
def view_past_attendance_by_id(member_id):
    past_attendance = gym_system.get_past_attendance(member_id)
    if past_attendance:
        return render_template('past_attendance_report.html', past_attendance=past_attendance)
    else:
        flash('No attendance data found for this member.')
        return redirect(url_for('view_past_attendance_form'))
    
@app.route('/delete_attendance', methods=['POST'])
def delete_attendance():
    if os.path.exists(ATTENDANCE_FILE):
        try:
            os.remove(ATTENDANCE_FILE)
            gym_system.attendance_obj.attendance = {}
            gym_system.attendance = {}
            flash('Attendance data deleted successfully!', 'success')
        except Exception as e:
            flash(f'Error deleting attendance data: {e}', 'error')
    else:
        flash('No attendance data found to delete.', 'error')
    return redirect(url_for('mark_attendance'))

# --------------------------
# Invoice Routes
# --------------------------
@app.route('/invoice', methods=['GET', 'POST'])
def generate_invoice():
    if request.method == 'POST':
        member_id = request.form['member_id'].strip()
        amount = request.form['amount'].strip()
        description = request.form.get('description', '').strip()
        due_date = request.form.get('due_date', '').strip()
        receiver_email = request.form['receiver_email'].strip()
        payment_method = request.form.get('payment_method', '').strip()  # New field
        
        member_id = str(member_id)
        
        # Check if the member is registered
        if member_id not in gym_system.members:
            flash('Member ID not found.', 'error')
            return redirect(url_for('generate_invoice'))
        
        # Generate the invoice if member exists
        if gym_system.generate_invoice(member_id, amount, description, due_date, payment_method):
            invoice = gym_system.invoices[-1]
            invoice["receiver_email"] = receiver_email
            flash(f'Invoice generated successfully for Member ID: {member_id}', 'success')
            
            filename = f"invoice_{invoice['invoice_id']}.pdf"
            generate_invoice_pdf(member_id, invoice['invoice_id'], amount, description, due_date, filename, payment_method)
            
            # Prepare the pending payment email
            subject = f"Your Invoice #{invoice['invoice_id']} - Payment Pending"
            body = (f"Dear Member,\n\n"
                    f"An invoice has been generated for you. Your payment is currently pending.\n\n"
                    f"Invoice ID: {invoice['invoice_id']}\n"
                    f"Amount Due: ₹{amount}\n"
                    f"Due Date: {due_date}\n"
                    f"Payment Method: {payment_method}\n\n"
                    "Please complete the payment by the due date to avoid any late fees.\n\n"
                    "Best Regards,\nGym Management Team")
            
            if send_email_with_invoice(receiver_email, subject, body, filename):
                flash(f'Invoice email sent to {receiver_email}', 'success')
            else:
                flash('Invoice generated but email sending failed.', 'error')
        else:
            flash('Invoice generation failed.', 'error')
        return redirect(url_for('view_invoices'))
    return render_template('generate_invoice.html')

@app.route('/view_invoices')
def view_invoices():
    invoices = gym_system.invoices
    return render_template('view_invoices.html', invoices=invoices)

@app.route('/mark_paid/<int:invoice_id>', methods=['POST'])
def mark_paid(invoice_id):
    for invoice in gym_system.invoices:
        if invoice["invoice_id"] == invoice_id:
            invoice["status"] = "Paid"
            flash(f"Invoice {invoice_id} marked as Paid!", "success")
            
            # Send a payment confirmation email after marking as paid
            receiver_email = invoice.get("receiver_email", "")
            subject = f"Payment Confirmation for Invoice #{invoice['invoice_id']}"
            body = (f"Dear Member,\n\n"
                    f"We have received your payment for Invoice #{invoice['invoice_id']}.\n"
                    f"Amount Paid: ₹{invoice['amount']}\n"
                    f"Date Issued: {invoice['date_issued']}\n\n"
                    "Thank you for your prompt payment.\n\n"
                    "Best Regards,\nGym Management Team")
            if send_email_with_invoice(receiver_email, subject, body, None):
                flash(f'Payment confirmation email sent to {receiver_email}', 'success')
            else:
                flash('Payment confirmation email sending failed.', 'error')
            gym_system.save_invoices()  # Save changes after marking as paid
            return redirect(url_for('view_invoices'))
    flash("Invoice not found!", "danger")
    return redirect(url_for('view_invoices'))

@app.route('/past_invoices')
def past_invoices():
    invoices = gym_system.invoices  # List of invoice dictionaries

    # Retrieve query parameters
    search_query = request.args.get('search', '').strip().lower()
    sort_by = request.args.get('sort_by', '').strip()
    filter_status = request.args.get('filter_status', '').strip()

    # Debug: print received parameters
    print("Received parameters:")
    print("  search_query:", search_query)
    print("  sort_by:", sort_by)
    print("  filter_status:", filter_status)

    # 1. Apply search filtering (member_id and description)
    if search_query:
        invoices = [
            inv for inv in invoices 
            if search_query in str(inv.get('member_id', '')).lower() or 
               search_query in str(inv.get('description', '')).lower()
        ]
        print("After search filter, invoice count:", len(invoices))

    # 2. Apply status filtering (case-insensitive)
    if filter_status:
        invoices = [
            inv for inv in invoices 
            if str(inv.get('status', '')).strip().lower() == filter_status.lower()
        ]
        print("After status filter, invoice count:", len(invoices))

    # 3. Apply sorting
    if sort_by:
      try:
        if sort_by == 'highest_amount':
            # Sort descending by amount
            invoices = sorted(invoices, key=lambda inv: float(inv.get('amount', 0)), reverse=True)
        elif sort_by == 'lowest_amount':
            # Sort ascending by amount
            invoices = sorted(invoices, key=lambda inv: float(inv.get('amount', 0)))
        elif sort_by == 'recent_first':
            # Sort descending by date_issued (most recent first)
            invoices = sorted(
                invoices,
                key=lambda inv: datetime.strptime(inv.get('date_issued', '1970-01-01'), "%Y-%m-%d"),
                reverse=True
            )
        elif sort_by == 'date':
            # Sort ascending by date_issued (oldest first)
            invoices = sorted(
                invoices,
                key=lambda inv: datetime.strptime(inv.get('date_issued', '1970-01-01'), "%Y-%m-%d")
            )
        elif sort_by == 'member_id':
            # Sort alphabetically by member_id
            invoices = sorted(invoices, key=lambda inv: str(inv.get('member_id', '')).lower())
        else:
            invoices = sorted(invoices, key=lambda inv: str(inv.get(sort_by, '')).lower())
        if invoices:
            print("After sorting, first invoice:", invoices[0])
      except Exception as e:
        print("Error during sorting:", e)
      except Exception as e:
        print("Error during sorting:", e)


    return render_template('past_invoices.html', invoices=invoices)



@app.route('/delete_invoice/<int:invoice_id>', methods=['POST'])
def delete_invoice(invoice_id):
    invoice = next((inv for inv in gym_system.invoices if inv["invoice_id"] == invoice_id), None)
    if invoice:
        gym_system.invoices.remove(invoice)
        flash(f"Invoice {invoice_id} deleted successfully.", "success")
    else:
        flash("Invoice not found.", "danger")
    return redirect(url_for('past_invoices'))

# --------------------------
# Reports and Member Endpoints
# --------------------------
@app.route('/reports')
def view_reports():
    members = gym_system.get_all_members()
    return render_template('reports.html', members=members)

@app.route('/members')
def list_members():
    members = gym_system.get_all_members()
    return render_template('members.html', members=members)

@app.route('/member/view/<member_id>', methods=['GET'])
def view_member(member_id):
    member = gym_system.members.get(member_id)
    if not member:
        flash("Member not found!", "error")
        return redirect(url_for('list_members'))
    return render_template('view_member.html', member=member)

@app.route('/member/edit/<member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    member = gym_system.members.get(member_id)
    if not member:
        flash("Member not found!", "error")
        return redirect(url_for('list_members'))

    if request.method == 'POST':
        data = request.form
        if "name" in data:
            member["name"] = data["name"]
        if "age" in data:
            member["age"] = data["age"]
        if "membership_type" in data:
            member["membership_type"] = data["membership_type"]
        if "pricing_period" in data:
            member["pricing_period"] = data["pricing_period"]
        if "pricing_amount" in data:
            member["pricing_amount"] = data["pricing_amount"]
        if "date_of_joining" in data: 
            member["date_of_joining"] = data["date_of_joining"]
        if "email" in data:
            member["email"] = data["email"]
        if "address" in data:
            member["address"] = data["address"]
        gym_system.members[member_id] = member
        gym_system.save_members()

        flash("Member updated successfully!", "success")
        return redirect(url_for('list_members'))

    return render_template('edit_member.html', member=member)

@app.route('/member/delete/<member_id>', methods=['DELETE'])
def delete_member(member_id):
    if member_id in gym_system.members:
        del gym_system.members[member_id]
        gym_system.save_members()
        return jsonify({"message": "Member deleted successfully!"}), 200
    else:
        return jsonify({"error": "Member not found"}), 404

# --------------------------
# Export Route
# --------------------------
@app.route('/export')
def export_members():
    members = gym_system.get_all_members()
    csv_string = StringIO()
    fieldnames = ["member_id", "name", "age", "membership_type", "date_of_joining", "pricing_period", "pricing_amount", "email", "address"]
    writer = csv.DictWriter(csv_string, fieldnames=fieldnames)
    writer.writeheader()
    for member in members:
        writer.writerow(member)
    
    csv_data = csv_string.getvalue()
    csv_string.close()
    bytes_io = BytesIO()
    bytes_io.write(csv_data.encode('utf-8'))
    bytes_io.seek(0)
    
    return send_file(
        bytes_io,
        mimetype='text/csv',
        as_attachment=True,
        download_name='members.csv'
    )

# --------------------------
# Dashboard / AI Endpoints
# --------------------------
@app.route('/dashboard')
def dashboard():
    analytics_data = {
        "total_members": len(gym_system.members),
        "attendance_trend": [30, 45, 28, 50, 60, 40, 35],
        "attendance_labels": ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
        "recent_registrations": list(gym_system.members.values())[-5:]
    }
    return render_template('dashboard.html', analytics=analytics_data)

if __name__ == '__main__':
    app.run(debug=True)
