# HE THONG QUAN LY KHO HANG PHAN TAN DA CHI NHANH (DISTRIBUTED WMS)

He thong Quan ly Kho hang Phan tan (Distributed Warehouse Management System) duoc thiet ke theo kien truc Vi dich vu (Microservices) chia se khong gian luu tru doc lap (Shared-Nothing Architecture), mo hinh giao tiep bat dong bo Event-driven qua RabbitMQ Topic Exchange, ap dung cac nguyen ly cot loi cua He thong phan tan: Dinh ly CAP (AP + Eventual Consistency), Saga Pattern, Outbox Pattern, Idempotency va Optimistic Concurrency Control.

---

## 1. TONG QUAN KIEN TRUC VA CAC NODE HE THONG

He thong bao gom 3 Node dich vu doc lap hoan toan va Message Broker:

1. **Node Tru so chinh (HQ Service - Cong 8000):**
   - Dong vai tro Master Data Catalog: Quan ly danh muc hang hoa goc, chinh sach don gia.
   - Dong vai tro Saga Coordinator: Dieu phoi cac don dieu chuyen kho lien chi nhanh.
   - Global Read-Model Snapshot (CQRS): Thu thap va luu tru ban chup ton kho toan quoc de phuc vu tra cuu tong the.
2. **Node Chi nhanh Ha Noi (Branch HN - Cong 8001):**
   - Co CSDL rieng biet (db_branch_hn.db), quan ly ton kho noi bo tai Ha Noi.
   - Tien trinh nen Outbox Worker rieng, dam bao tinh tu tri cuc bo (Local Autonomy).
3. **Node Chi nhanh TP.HCM (Branch HCM - Cong 8002):**
   - Co CSDL rieng biet (db_branch_hcm.db), quan ly ton kho noi bo tai TP.HCM.
   - Tien trinh nen Outbox Worker rieng, tiep nhan va xac nhan/tu choi cac kien hang dieu chuyen.
4. **Message Broker (RabbitMQ - Cong 5672 AMQP, 15672 Web Management):**
   - Topic Exchange 'distributed_warehouse' ket noi va phan phoi su kien giua cac node mot cach bat dong bo.
5. **Giao dien Nguoi dung (Frontend ReactJS - Cong 3000):**
   - Dashboard quan tri phan tach Route doc lap theo tung kho, xac thuc JWT Bearer Token va phan quyen chat che.

---

## 2. BANG DIA CHI VA CONG TRUY CAP DICH VU

| Thanh phan | Dia chi URL | Chuc nang |
| :--- | :--- | :--- |
| **Giao dien Web (Frontend)** | http://localhost:3000 | Web Dashboard quan tri he thong |
| **Node Tru so chinh (HQ)** | http://localhost:8000/docs | Swagger REST API Tru so chinh |
| **Node Chi nhanh Ha Noi (HN)** | http://localhost:8001/docs | Swagger REST API Chi nhanh Ha Noi |
| **Node Chi nhanh TP.HCM (HCM)** | http://localhost:8002/docs | Swagger REST API Chi nhanh TP.HCM |
| **RabbitMQ Management** | http://localhost:15672 | Quan tri Message Broker (guest / guest) |
| **MSSQL Database** | localhost:14333 | CSDL quan he Microsoft SQL Server |

---

## 3. HUONG DAN CAI DAT VA KHOI CHAY (QUICK START)

### 3.1. Yeu cau he thong
- Da cai dat Docker Desktop va Docker Compose (hoac WSL2 tren Windows).
- Python 3.11+ (dung de chay cac kịch ban kiem thu tu dong trong thu muc tests/).

### 3.2. Khoi chay toan bo he thong bang Docker Compose
Mo Terminal (PowerShell hoac Bash) tai thu muc goc cua du an va chay lenh:

```bash
docker compose up -d --build
```

Lenh tren se tu dong bien dich va khoi chay 6 container:
- `rabbitmq_wms`
- `sqlserver_wms`
- `hq_service`
- `branch_hn`
- `branch_hcm`
- `frontend_wms`

### 3.3. Kiem tra trang thai hoat dong cua cac Service
Sau khi cac container khoi dong khoang 15-20 giay, kiem tra endpoint suc khoe (Health check):

```bash
# Kiem tra ket noi giua 3 node backend voi RabbitMQ Broker
curl -s http://localhost:8000/health
curl -s http://localhost:8001/health
curl -s http://localhost:8002/health
```
Ket qua tra ve phai co `status: "UP"` va `broker_connected: true`.

*Luu y:* Neu RabbitMQ vua khoi dong lan dau can vai giay de mo cong 5672, neu thay `broker_connected: false`, chi can khoi dong lai 3 backend:
```bash
docker restart hq_service branch_hn branch_hcm
```

### 3.4. Dung he thong
Khi can tat toan bo cuem dich vu:
```bash
docker compose down
```

---

## 4. HE THONG TAI KHOAN VA PHAN QUYEN (RBAC & JWT)

He thong phan tach Route va tai khoan ro rang theo vai tro tai `http://localhost:3000/login`:

| Tai khoan | Mat khau | Vai tro (Role) | Chi nhanh | Pham vi quyen han |
| :--- | :--- | :--- | :--- | :--- |
| **admin** | admin123 | HQ_MANAGER | HQ | Toan quyen quan tri Tru so chinh: CRUD Master Catalog, phan bo ton dau ky, phat lenh dieu chuyen Saga, giam sat toan quoc. |
| **manager_hn** | hn123 | BRANCH_MANAGER | HN | Quan tri Chi nhanh Ha Noi: Xuat/nhap tai cho, duyet kien hang den, kiem ke kho thuc te. Khong duoc sua du lieu kho khac. |
| **manager_hcm** | hcm123 | BRANCH_MANAGER | HCM | Quan tri Chi nhanh TP.HCM: Tuong tu Ha Noi, chi thao tac tren du lieu kho TP.HCM. |
| **staff_hn** | staff123 | BRANCH_STAFF | HN | Thu kho Ha Noi: Thuc hien xuat nhap, kiem ke tai ke. |
| **staff_hcm** | staff123 | BRANCH_STAFF | HCM | Thu kho TP.HCM: Thuc hien xuat nhap, kiem ke tai ke. |

*Ghi chu:* Tren man hinh dang nhap `/login` co san khay **"Tai khoan mau bao cao do an (Quick Login)"** gom 4 nut an de ban co the click dang nhap nhanh ngay lap tuc ma khong can go phim.

---

## 5. PHAN TACH ROUTE VA CAC TRANG CHUC NANG

### 5.1. Trang Dang Nhap (`/login`)
- Xac thuc thong qua REST API `POST /api/v1/auth/login` cap token JWT Bearer.
- Tu dong luu token vao `localStorage` va chuyen huong ve dung trang cua vai tro tuong ung.

### 5.2. Trang Quan tri Tru so chinh (`/hq` hoac `/`)
- Chi danh cho tai khoan `HQ_MANAGER`.
- **Quan ly Danh muc Hang hoa (Master Catalog):**
  + Nut *Thêm Mat Hang Moi*: Cho phep nhap thong tin san pham va chi dinh luon Ton dau ky cho Kho Ha Noi va Kho TP.HCM. Su kien `evt.catalog.product_created` se tu dong phat tan dong bo ve CSDL cua ca 2 chi nhanh.
  + Nut *Sua*: Chinh sua ten, don vi tinh, don gia, dinh muc ton an toan Min/Max.
  + Nut *Xoa*: Tich hop co che bao ve toan ven du lieu (Delete Protection), chi cho phep xoa khi toan bo ton kho tren toan he thong bang 0.
- **Dieu phoi Saga (Saga Coordinator):**
  + Form tao don dieu chuyen kho giua Ha Noi va TP.HCM.
  + Bang nhat ky dong thoi gian Saga (Saga Timeline): Theo doi cac trang thai `INITIATED`, `RESERVED_IN_TRANSIT`, `COMPLETED`, `COMPENSATING`, `CANCELLED_ROLLED_BACK`.
- **Bo Gia lap Su co Phan tan (Network Chaos Simulator):**
  + Trinh dien 3 dac tinh phan tan: Tinh tu tri cuc bo (Local Autonomy), Kha nang tu phuc hoi sau sup nguon (Crash Recovery) va Saga Coordinator Timeout.
- **Thanh Giam sat Nhanh:** Co the bam sang xem goc nhin cua Kho Ha Noi va Kho TP.HCM.

### 5.3. Trang Chi nhanh Ha Noi (`/branch/hn`) va TP.HCM (`/branch/hcm`)
- Danh rieng cho nhan su cua tung chi nhanh tuong ung.
- **Nghiep vu Kho Cuc bo (Local Autonomy):**
  + Tab *Xuat Ban / Nhap Mua*: Nhap hang tu Nha cung cap hoac Xuat ban cho Khach hang kem so hoa don va ghi chu.
  + Tab *Kiem Ke Thuc Te*: Nhap so luong dem thuc te tai ke, he thong tu dong tinh toan muc chenh lech va can doi so du so sach.
  + Thiet lap Dinh muc Ton kho Min/Max de kich hoat co canh bao thieu hang `is_low_stock`.
- **Tiep nhan Kien hang Chuyen kho (Incoming Transfers):**
  + Xem danh sach cac kien hang dang tren duong chuyen toi chi nhanh.
  + Nut *Xac Nhan Nhap Kho*: Hoan tat don Saga thanh cong (`COMPLETED`).
  + Nut *Tu Choi Nhan Hang*: Kich hoat quy trinh bu tru hoan tac (`Saga Rollback`), tra hang ve kho nguon.
- **Bang Doi soat Ton kho Toan quoc (Read-Only):**
  + Xem so lieu ton kho toan he thong o che do Chi doc (an cac nut tao/sua/xoa).
- **Rao chan Bao ve Phap quy (RBAC Guard):**
  + Neu nhan vien kho HN co tinh truy cap `/branch/hcm`, he thong se chan va bao loi 403 Forbidden.

---

## 6. HUONG DAN KIEM THU TU DONG QUA TERMINAL (TEST SUITES)

Tat ca cac kich ban kiem thu phan tan da duoc dong goi thanh cac script Python doc lap trong thu muc `tests/`.

### 6.1. Chay toan bo bo kiem thu (Khuyen nghi)
Mo PowerShell tai thu muc goc cua du an va chay:

```powershell
$env:PYTHONIOENCODING="utf-8"

# 1. Kiem thu Saga dieu chuyen thanh cong (Happy Path)
python tests/test_saga_happy_path.py

# 2. Kiem thu Giao dich bu tru Saga Rollback khi kho dich tu choi
python tests/test_saga_rollback.py

# 3. Kiem thu 10 yeu cau dong thoi chong am kho (Race Condition & Optimistic Locking)
python tests/test_concurrency_race_condition.py

# 4. Kiem thu Tinh nang nang cap toan dien (JWT Auth, Catalog Replication, Audit, Persist DB)
python tests/test_new_enhancements.py

# 5. Kiem thu CRUD San pham, Phan bo ton dau ky HN/HCM va Rang buoc xoa an toan
python tests/test_crud_refinement.py
```

### 6.2. Y nghia ket qua cac bai test
- `test_saga_happy_path.py`: Kho HN giam 20, kho HCM tang 20, Saga HQ dat `COMPLETED`.
- `test_saga_rollback.py`: Kho HCM tu choi nhan hang, Saga Coordinator phat lenh bu tru `CMD_RELEASE_STOCK`, kho HN duoc hoan tra day du so hang tam khoa ve ton kha dung, don chuyen sang `CANCELLED_ROLLED_BACK`.
- `test_concurrency_race_condition.py`: Ban dong thoi 10 request doi xuat 150 san pham trong khi ton chi co 80. He thong chap thuan dung 5 request (75 san pham), chan 5 request con lai, ton con dung 5, tuyet doi khong bi am kho.
- `test_crud_refinement.py`: Tao san pham tai HQ kem so ton kho HN va HCM, kiem tra CSDL chi nhanh tu dong nhan su kien va luu but toan `INITIAL_STOCK`, kiem tra co che chan xoa san pham khi con ton kho.

---

## 7. CAU TRUC THU MUC DU AN

```
Khohang_phantan/
├── backend/
│   ├── branch_service/              # Node Chi nhanh (FastAPI)
│   │   ├── consumers/               # RabbitMQ consumer lang nghe lenh dieu phoi
│   │   ├── routers/                 # API ton kho, kien hang den, kiem ke
│   │   ├── services/                # Xu ly nghiep vu ton kho va Outbox Worker
│   │   └── models.py                # Mo hinh CSDL SQLite cuc bo
│   ├── hq_service/                  # Node Tru so chinh (FastAPI)
│   │   ├── routers/                 # API danh muc, dieu chuyen Saga, snapshot
│   │   ├── services/                # Saga Timeout Worker tu phuc hoi
│   │   └── models.py                # Mo hinh CSDL Master Catalog & Snapshots
│   └── shared/                      # Thu vien dung chung
│       ├── auth.py                  # Module xac thuc HMAC-SHA256 Token & RBAC
│       ├── event_schemas.py         # Hop dong thong diep Pydantic
│       └── rabbitmq_client.py       # Wrapper ket noi Topic Exchange bat dong bo
├── frontend/                        # Web Dashboard (ReactJS + Vite + TailwindCSS)
│   └── src/
│       ├── components/              # GlobalStockTable, LocalBranchPanel, ChaosSimulator...
│       ├── context/                 # AuthContext quan ly JWT session
│       ├── pages/                   # LoginPage, HQDashboardPage, BranchDashboardPage
│       ├── api/client.js            # Client goi REST API kem Authorization header
│       └── App.jsx                  # Root container va Route Dispatcher
├── tests/                           # Cac tap tin kiem thu phan tan tu dong
├── Implement/                       # Nhat ky tien do trien khai chi tiet theo ngay
├── docker-compose.yml               # Cau hinh khoi chay toan bo 6 container
└── README.md                        # Tai lieu huong dan du an nay
```

---

## 8. TAI LIEU THAM KHAO BO SUNG
- **Huong dan Thuyet trinh va Bo cau hoi phan bien Do an:** Xem file `HUONG_DAN_TEST_VA_KICH_BAN_BAO_CAO_DO_AN_UDPT.md`.
- **Nhat ky Trien khai Chi tiet:** Xem cac file tong ket tai thu muc `Implement/2026-11-09.md` va `Implement/2026-11-10.md`.
