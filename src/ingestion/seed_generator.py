"""
Enterprise Seed Data Generator for AI-Ready Enterprise Data Platform.
Generates:
1. Structured OLTP Relational Seed Data (Customers, Products, Orders, Order_Items)
2. Realistic Enterprise Documents:
   - PDF: Commercial VIP Distribution Agreement with SLA terms (CONFIDENTIAL)
   - DOCX: Sales Return & Warranty Policy (PUBLIC)
   - XML: Warehouse & Logistics SOP (INTERNAL)
   - XLSX: Q1 Internal Financial & Tax Audit Report (RESTRICTED)
"""

import os
import random
import datetime
import sqlite3
import xml.etree.ElementTree as ET
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import docx
import openpyxl


def generate_seed_data(base_dir: str = "./data"):
    os.makedirs(f"{base_dir}/raw_documents", exist_ok=True)
    os.makedirs(f"{base_dir}/seed_oltp", exist_ok=True)

    print("Generating Structured OLTP Data...")
    _generate_oltp_database(f"{base_dir}/seed_oltp/oltp_ecommerce.db")

    print("Generating Unstructured Enterprise Documents...")
    _generate_pdf_contract(f"{base_dir}/raw_documents/CTR_2026_VIP_001_NorthDistribution.pdf")
    _generate_docx_policy(f"{base_dir}/raw_documents/POL_2026_Return_Warranty_Policy.docx")
    _generate_xml_sop(f"{base_dir}/raw_documents/SOP_2026_Warehouse_ColdChain_Handling.xml")
    _generate_xlsx_audit(f"{base_dir}/raw_documents/AUD_2026_Q1_Financial_Audit_Report.xlsx")

    print("Seed generation completed successfully!")


def _generate_oltp_database(db_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS order_items")
    cur.execute("DROP TABLE IF EXISTS orders")
    cur.execute("DROP TABLE IF EXISTS products")
    cur.execute("DROP TABLE IF EXISTS customers")

    cur.execute("""
        CREATE TABLE customers (
            customer_id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            tier TEXT NOT NULL, -- 'VIP', 'TIER_1', 'TIER_2', 'STANDARD'
            tenant_id TEXT NOT NULL, -- 'VN_DIST_NORTH', 'VN_DIST_SOUTH'
            contact_email TEXT NOT NULL,
            credit_limit REAL NOT NULL,
            region TEXT NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE products (
            product_id TEXT PRIMARY KEY,
            sku TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit_cost REAL NOT NULL,
            unit_price REAL NOT NULL,
            stock_quantity INTEGER NOT NULL,
            created_at TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            order_number TEXT UNIQUE NOT NULL,
            customer_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            order_date TIMESTAMP NOT NULL,
            status TEXT NOT NULL, -- 'DELIVERED', 'SHIPPED', 'CANCELLED', 'RETURNED'
            total_amount REAL NOT NULL,
            shipping_hours INTEGER NOT NULL,
            sla_target_hours INTEGER NOT NULL,
            sla_breached INTEGER NOT NULL, -- 0 or 1
            created_at TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        )
    """)

    cur.execute("""
        CREATE TABLE order_items (
            item_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            discount_rate REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (order_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        )
    """)

    # Customers Seed
    customers = [
        ("CUST-001", "Tập đoàn Phân phối Miền Bắc (VIP North)", "VIP", "VN_DIST_NORTH", "procurement@northdist.vn", 500000.0, "NORTH"),
        ("CUST-002", "Công ty CP Bán lẻ Á Châu (Asia Retail)", "TIER_1", "VN_DIST_NORTH", "orders@asiaretail.com", 250000.0, "NORTH"),
        ("CUST-003", "Hệ thống Siêu thị Phương Nam (South Market)", "VIP", "VN_DIST_SOUTH", "supply@southmarket.vn", 600000.0, "SOUTH"),
        ("CUST-004", "Chuỗi Bách hóa Tân Bình", "TIER_2", "VN_DIST_SOUTH", "tanbinh@store.vn", 100000.0, "SOUTH"),
        ("CUST-005", "Đại lý Bán buôn Hà Đông", "STANDARD", "VN_DIST_NORTH", "hadong@wholesale.vn", 50000.0, "NORTH"),
    ]
    cur.executemany("""
        INSERT INTO customers (customer_id, company_name, tier, tenant_id, contact_email, credit_limit, region, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, '2026-01-01 08:00:00', '2026-01-01 08:00:00')
    """, customers)

    # Products Seed
    products = [
        ("PROD-001", "SKU-ELEC-4K-01", "Màn hình 4K Doanh nghiệp 32 inch", "Electronics", 280.0, 450.0, 150),
        ("PROD-002", "SKU-ELEC-SRV-02", "Máy chủ Edge Server Enterprise AI", "Hardware", 2100.0, 3200.0, 45),
        ("PROD-003", "SKU-LOGI-PAL-03", "Pallet Thông minh Định vị GPS/IoT", "Logistics", 45.0, 85.0, 500),
        ("PROD-004", "SKU-NETW-SWT-04", "Switch Quang 48 Port 10Gbps Managed", "Networking", 650.0, 980.0, 80),
        ("PROD-005", "SKU-CBL-CAT6-05", "Cuộn Cáp Mạng Cat6 chống nhiễu 305m", "Accessories", 60.0, 110.0, 320),
    ]
    cur.executemany("""
        INSERT INTO products (product_id, sku, product_name, category, unit_cost, unit_price, stock_quantity, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, '2026-01-01 09:00:00')
    """, products)

    # Orders & Order Items Seed
    random.seed(42)
    orders = []
    order_items = []
    base_date = datetime.datetime(2026, 1, 15, 10, 0, 0)

    for i in range(1, 101):
        order_id = f"ORD-{i:04d}"
        order_num = f"SO-2026-{i:04d}"
        cust = random.choice(customers)
        cust_id, _, tier, tenant_id, _, _, region = cust

        order_time = base_date + datetime.timedelta(days=random.randint(0, 75), hours=random.randint(0, 23))
        
        # VIP SLA target: 24h, non-VIP: 48h
        sla_target = 24 if tier == "VIP" else 48
        
        # Intentionally create some breached deliveries for CUST-001 to test SLA penalty cross-analysis!
        if cust_id == "CUST-001" and i % 3 == 0:
            shipping_hours = random.randint(32, 54) # BREACHED
        else:
            shipping_hours = random.randint(12, sla_target)
        
        sla_breached = 1 if shipping_hours > sla_target else 0
        status = random.choice(["DELIVERED", "DELIVERED", "DELIVERED", "SHIPPED", "RETURNED"])
        if sla_breached and random.random() < 0.3:
            status = "RETURNED"

        # Items
        num_items = random.randint(1, 3)
        order_total = 0.0
        selected_prods = random.sample(products, num_items)
        for idx, prod in enumerate(selected_prods):
            prod_id, sku, name, cat, cost, price, stock = prod
            qty = random.randint(2, 20)
            discount = 0.05 if tier == "VIP" else 0.0
            subtotal = qty * price * (1.0 - discount)
            order_total += subtotal
            item_id = f"ITEM-{i:04d}-{idx+1}"
            order_items.append((item_id, order_id, prod_id, qty, price, discount, round(subtotal, 2)))

        orders.append((
            order_id, order_num, cust_id, tenant_id, 
            order_time.strftime("%Y-%m-%d %H:%M:%S"), status, 
            round(order_total, 2), shipping_hours, sla_target, sla_breached,
            order_time.strftime("%Y-%m-%d %H:%M:%S")
        ))

    cur.executemany("""
        INSERT INTO orders (order_id, order_number, customer_id, tenant_id, order_date, status, total_amount, shipping_hours, sla_target_hours, sla_breached, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, orders)

    cur.executemany("""
        INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price, discount_rate, subtotal)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, order_items)

    conn.commit()
    conn.close()


def _generate_pdf_contract(pdf_path: str):
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter

    # Page 1
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, "CONG HOA XA HOI CHU NGHIA VIET NAM")
    c.setFont("Helvetica", 11)
    c.drawString(50, height - 70, "Doc lap - Tu do - Hanh phuc")
    c.drawString(50, height - 90, "---------------------------------------------")

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, height - 120, "HOP DONG PHAN PHOI THUONG MAI CHIEN LUOC VIP")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 140, "HOP DONG SO: CTR-2026-VIP-001")
    c.drawString(50, height - 155, "TENANT ID: VN_DIST_NORTH")
    c.drawString(50, height - 170, "PHONG BAN: SALES")
    c.drawString(50, height - 185, "PHAN LOAI BAO MAT: CONFIDENTIAL")
    c.drawString(50, height - 200, "NGAY HIEU LUC: 2026-01-01")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 230, "DIEU 1: CAC BEN THAM GIA")
    c.setFont("Helvetica", 10)
    c.drawString(60, height - 245, "BEN A (Nha Cung Cap): Tap doan Cong nghe Du lieu Doanh nghiep.")
    c.drawString(60, height - 260, "BEN B (Dai dien Phan Phoi VIP): Tap doan Phan phoi Mien Bac (VIP North, CUST-001).")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 290, "DIEU 2: CAM KET MUC DO DICH VU (SLA DELIVERY COMMITMENT)")
    c.setFont("Helvetica", 10)
    c.drawString(60, height - 310, "1. Thoi gian giao hang chuan (DELIVERY SLA): BEN A cam ket giao hang trong vong 24 GIO (24 HOURS)")
    c.drawString(60, height - 325, "   ke tu thoi diem he thong ghi nhan don hang vao kho tap ket.")
    c.drawString(60, height - 340, "2. Dieu khoan boi thuong phat SLA (SLA PENALTY): Neu thoi gian giao hang vuot qua 24 gio,")
    c.drawString(60, height - 355, "   BEN A chiu muc PHAT CHAM GIAO HANG la 2.5% gia tri don hang cho moi 12 gio tre han.")
    c.drawString(60, height - 370, "3. Truong hop don hang bi tre tren 48 gio, BEN B co quyen tu choi nhan hang (RETURNED)")
    c.drawString(60, height - 385, "   va BEN A phai hoan tra 100% chi phi kem muc phat toi da 10% gia tri hop dong don hang.")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 415, "DIEU 3: CHINH SACH CHIET KHAU & HAN MUC TIN DUNG")
    c.setFont("Helvetica", 10)
    c.drawString(60, height - 435, "- Han muc cong no phe duyet: 500,000.00 USD.")
    c.drawString(60, height - 450, "- Muc chiet khau thuong mai co dinh ap dung cho Doi tac VIP: 5% tren toan bo danh muc san pham.")

    c.showPage()
    c.save()


def _generate_docx_policy(docx_path: str):
    doc = docx.Document()
    doc.add_heading("CHÍNH SÁCH BÁN HÀNG, ĐỔI TRẢ VÀ BẢO HÀNH TOÀN QUỐC", level=1)
    
    doc.add_paragraph("MÃ TÀI LIỆU: POL-2026-RET-01")
    doc.add_paragraph("TENANT ID: GLOBAL_TENANT")
    doc.add_paragraph("PHÒNG BAN: LOGISTICS")
    doc.add_paragraph("PHÂN LOẠI BẢO MẬT: PUBLIC")
    doc.add_paragraph("NGÀY HIỆU LỰC: 2026-01-01")

    p = doc.add_paragraph()
    p.add_run("1. Quy định thời hạn đổi trả hàng hóa (Return Window):\n").bold = True
    p.add_run("Khách hàng và các đại lý có quyền khiếu nại hoặc yêu cầu đổi trả sản phẩm trong THỜI HẠN ĐỔI TRẢ: 14 NGÀY kể từ ngày nhận hàng thành công theo biên bản bàn giao.\n")

    p2 = doc.add_paragraph()
    p2.add_run("2. Điều kiện được chấp thuận đổi hàng:\n").bold = True
    p2.add_run("- Sản phẩm còn nguyên tem niêm phong, không có dấu hiệu va đập cơ học.\n")
    p2.add_run("- Lỗi phát sinh do nhà sản xuất hoặc do vi phạm điều kiện bảo quản trong quá trình vận chuyển.\n")
    p2.add_run("- Đơn vị kho vận cam kết kiểm định và cấp đơn đổi mới trong vòng 48 GIỜ làm việc.\n")

    table = doc.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Hạng mục Sản phẩm"
    hdr_cells[1].text = "Thời hạn Đổi trả"
    hdr_cells[2].text = "Phí Vận chuyển Phát sinh"

    data = [
        ("Thiết bị Điện tử & Máy chủ", "14 ngày", "Miễn phí 100%"),
        ("Thiết bị Mạng & Phụ kiện", "7 ngày", "Miễn phí 100%"),
        ("Pallet & Vật tư Kho bãi", "30 ngày", "Đại lý chi trả 50%")
    ]
    for row in data:
        row_cells = table.add_row().cells
        row_cells[0].text = row[0]
        row_cells[1].text = row[1]
        row_cells[2].text = row[2]

    doc.save(docx_path)


def _generate_xml_sop(xml_path: str):
    root = ET.Element("StandardOperatingProcedure")
    root.set("id", "SOP-2026-WH-04")
    root.set("security_acl", "INTERNAL")

    meta = ET.SubElement(root, "Metadata")
    ET.SubElement(meta, "Title").text = "Quy trình Vận hành Kho Bãi & Quản lý Chuỗi Cung ứng"
    ET.SubElement(meta, "TenantId").text = "GLOBAL_TENANT"
    ET.SubElement(meta, "Department").text = "WAREHOUSE"
    ET.SubElement(meta, "SecurityClassification").text = "INTERNAL"
    ET.SubElement(meta, "EffectiveDate").text = "2026-01-01"

    rules = ET.SubElement(root, "OperationalRules")
    
    rule1 = ET.SubElement(rules, "Rule")
    rule1.set("code", "RULE-DISPATCH-01")
    ET.SubElement(rule1, "Description").text = "Mọi đơn hàng ưu tiên của khách hàng VIP phải được xuất kho trong vòng 4 giờ kể từ khi duyệt đơn."

    rule2 = ET.SubElement(rules, "Rule")
    rule2.set("code", "RULE-STORAGE-02")
    ET.SubElement(rule2, "Description").text = "Hàng hóa nhóm Electronics và Server Enterprise phải lưu trữ tại kho nhiệt độ phòng 20-25 độ C, độ ẩm dưới 60%."

    tree = ET.ElementTree(root)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)


def _generate_xlsx_audit(xlsx_path: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Executive_Audit_Summary"

    ws.append(["MÃ BÁO CÁO", "AUD-2026-Q1-FIN"])
    ws.append(["TENANT ID", "GLOBAL_TENANT"])
    ws.append(["PHÒNG BAN", "FINANCE"])
    ws.append(["PHÂN LOẠI BẢO MẬT", "RESTRICTED"])
    ws.append(["NGÀY HIỆU LỰC", "2026-03-31"])
    ws.append([])
    ws.append(["BÁO CÁO KIỂM TOÁN TÀI CHÍNH NỘI BỘ QUÝ 1/2026 - TỐI MẬT"])
    ws.append(["Lưu ý: Chỉ Giám đốc Tài chính (CFO), CEO và Ban Kiểm soát (RESTRICTED clearance) được phép truy cập."])
    ws.append([])
    ws.append(["Khu vực", "Tổng Doanh thu Gộp (USD)", "Giá vốn Hàng bán COGS (USD)", "Lợi nhuận Gộp (Gross Margin)", "Chi phí Thưởng Ban Điều hành"])
    ws.append(["Miền Bắc (VN_DIST_NORTH)", 1450000.0, 920000.0, "36.5%", 180000.0])
    ws.append(["Miền Nam (VN_DIST_SOUTH)", 1820000.0, 1150000.0, "36.8%", 220000.0])
    ws.append(["Tổng Hợp Doanh Nghiệp", 3270000.0, 2070000.0, "36.7%", 400000.0])

    wb.save(xlsx_path)


if __name__ == "__main__":
    generate_seed_data()
