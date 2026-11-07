# tests/test_concurrency_race_condition.py
"""
KỊCH BẢN KIỂM THỬ 4: KIỂM SOÁT XUNG ĐỘT ĐỒNG THỜI (CONCURRENCY CONTROL & ROW LOCKING)
Mục tiêu:
Chứng minh hệ thống ngăn chặn tuyệt đối hiện tượng âm kho (Race Condition / Over-selling)
khi có nhiều yêu cầu xuất kho diễn ra cùng một thời điểm bằng cơ chế khóa dòng trên SQL Server (UPDLOCK)
hoặc kiểm tra phiên bản (Optimistic Locking).

Kịch bản:
- Kho có N sản phẩm khả dụng.
- Bắn đồng thời 10 yêu cầu xuất kho (mỗi yêu cầu đòi 5 sản phẩm) trong cùng 1 mili-giây.
- Kiểm tra: Tổng số sản phẩm được trừ thành công không bao giờ vượt quá N.
- Tồn kho cuối cùng tuyệt đối không bao giờ bị âm (< 0).
"""
import sys
import uuid
import asyncio
import httpx

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HN_URL = "http://localhost:8001/api/v1"

async def send_concurrent_requests():
    print("=" * 70)
    print(" KỊCH BẢN 4: KIỂM THỬ ĐỒNG THỜI (CONCURRENCY & RACE CONDITION TEST)")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Lấy số lượng khả dụng hiện tại
        sku = "CHUOT-LOGI-MX3"
        inv_res = await client.get(f"{HN_URL}/inventory")
        inv_data = {item["sku"]: item for item in inv_res.json()}
        start_avail = inv_data[sku]["available_qty"]

        print(f"\n[Bước 1] Tồn kho khả dụng hiện tại của SKU '{sku}' tại Kho HN: {start_avail} cái")
        
        # 2. Chuẩn bị 10 yêu cầu đồng thời, mỗi yêu cầu xuất 15 cái
        request_qty = 15
        num_requests = 10
        total_demanded = request_qty * num_requests
        print(f"[Bước 2] Chuẩn bị gửi ĐỒNG THỜI {num_requests} yêu cầu xuất kho (Mỗi yêu cầu: {request_qty} cái, Tổng đòi: {total_demanded} cái)...")

        run_id = uuid.uuid4().hex[:6].upper()
        async def worker(req_id: int):
            try:
                res = await client.post(f"{HN_URL}/inventory/adjust", json={
                    "sku": sku,
                    "change_type": "LOCAL_OUT",
                    "quantity": request_qty,
                    "reference_id": f"STRESS-{run_id}-{req_id}"
                })
                return req_id, res.status_code, res.json()
            except Exception as e:
                return req_id, 500, {"error": str(e)}

        # 3. Kích hoạt đồng thời bằng asyncio.gather
        print("\n[Bước 3] Đang bắn đồng thời 10 requests tới Node Chi nhánh HN...")
        tasks = [worker(i + 1) for i in range(num_requests)]
        results = await asyncio.gather(*tasks)

        # 4. Phân tích kết quả
        print("\n[Bước 4] Kết quả phản hồi của từng yêu cầu:")
        success_count = 0
        failed_count = 0

        for req_id, status_code, body in results:
            if status_code == 200 and body.get("status") == "SUCCESS":
                success_count += 1
                print(f" -> Req #{req_id:02d}: [THÀNH CÔNG] Đã xuất {request_qty} cái (Tồn còn lại: {body.get('available_qty')})")
            else:
                failed_count += 1
                reason = body.get("detail", body.get("reason", "Từ chối do hết hàng"))
                print(f" -> Req #{req_id:02d}: [BỊ TỪ CHỐI] Lý do: {reason}")

        # 5. Đối soát tồn kho cuối cùng
        inv_post_res = await client.get(f"{HN_URL}/inventory")
        inv_post = {item["sku"]: item for item in inv_post_res.json()}
        final_avail = inv_post[sku]["available_qty"]

        print("\n" + "-" * 70)
        print(f" TỔNG KẾT KIỂM THỬ ĐỒNG THỜI:")
        print(f" - Số yêu cầu thành công: {success_count} ({success_count * request_qty} sản phẩm)")
        print(f" - Số yêu cầu bị chặn:     {failed_count}")
        print(f" - Tồn kho ban đầu:        {start_avail}")
        print(f" - Tồn kho thực tế còn:    {final_avail}")
        print(f" - Kỳ vọng còn lại:        {start_avail - (success_count * request_qty)}")

        assert final_avail >= 0, f"NGHIÊM TRỌNG: TỒN KHO BỊ ÂM ({final_avail})! RACE CONDITION XẢY RA!"
        assert final_avail == start_avail - (success_count * request_qty), "Lỗi: Số lượng tồn kho không khớp với số giao dịch thành công!"

        print("-" * 70)
        print(" KẾT QUẢ: KIỂM SOÁT ĐỒNG THỜI HOÀN HẢO! KHÔNG BỊ ÂM KHO [PASSED]")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(send_concurrent_requests())
