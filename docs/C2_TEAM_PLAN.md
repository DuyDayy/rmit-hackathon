# Unsellable — Kế hoạch thực thi Challenge 2 (UNLOCKED)

**Deadline nộp:** Thứ Năm 22/10, **18:00 giờ VN** (Google Form, link repo public).
**Mốc nội bộ:** code freeze **16:45** · quay video **16:45–17:30** · push + nộp form **trước 17:45**.

Repo hiện chỉ có README (pitch + setup dự kiến). **Chưa có code app, chưa có realm TideCloak.** Mọi việc dưới đây tính từ con số 0.

---

## 0. Phạm vi demo (chốt, không mở rộng)

Chỉ làm 5 bước cốt lõi trong "Demo walkthrough" của README:

| # | Tính năng | Bắt buộc? |
|---|---|---|
| D1 | Đăng nhập qua TideCloak cho `maya`, `admin.acquirer`, `admin.company`, `custodian`, `ethics` | **Bắt buộc** |
| D2 | Maya seal genome tổng hợp (encrypt trong browser) → server chỉ lưu ciphertext → Maya mở lại được | **Bắt buộc** |
| D3 | Trang "Database view" hiển thị file DB thô: chỉ thấy ciphertext | **Bắt buộc** |
| D4 | `admin.acquirer` bấm "Export all genomes" → bị từ chối (không có quyền decrypt) | **Bắt buộc** |
| D5 | Acquirer tự cấp role đọc → change request **pending** cần quorum; `custodian` + `ethics` reject | **Bắt buộc** (có fallback, xem §4) |
| D6 | Researcher `lee` được quorum duyệt rồi đọc | **Cắt** — để "Planned" |
| D7 | Consent toggle (lưu plaintext, chỉ hiển thị) | Chỉ làm nếu dư ≥20 phút |

Nguyên tắc: README chỉ được ghi "Implemented" cho thứ thực sự có trong video.

---

## 1. Vai trò (4 luồng làm song song)

Gán người vào vai ngay phút đầu. Nếu team 3 người: gộp **C** vào **B**.

| Vai | Phụ trách | Đầu ra |
|---|---|---|
| **A — TideCloak/Infra** | Docker TideCloak, realm `unsellable`, client, roles, users, 3 quorum admin, file adapter | Realm chạy được + file adapter JSON gửi cho B |
| **B — Frontend** | App Next.js từ template TideCloak, các trang UI, gọi encrypt/decrypt | App chạy `npm run dev`, đủ trang D1–D5 |
| **C — Data/Backend** | API lưu/đọc ciphertext (file JSON), seed genome tổng hợp, trang Database view, nút Export | API + `data/genomes.json` |
| **D — Story/Submit** | README, kịch bản video, quay/dựng video, form nộp, test "clean machine" | `demo.mp4` < 100 MB, README khớp prototype, form đã nộp |

---

## 2. Danh sách task (rời rạc, có điều kiện tiên quyết và tiêu chí PASS)

Ký hiệu: **Pre** = phải xong trước · **PASS** = cách kiểm tra xong · **FAIL →** = làm gì nếu kẹt.

### Luồng A — TideCloak (đường găng, làm trước nhất)

| ID | Việc | Pre | PASS | FAIL → |
|---|---|---|---|---|
| A1 | Bật Docker Desktop; chạy container TideCloak dev (lệnh trong README §Setup 1). Mount `.tidecloak-data/` nếu muốn giữ dữ liệu (đã có trong `.gitignore`) | — | Mở `http://localhost:8080`, đăng nhập admin console | Hỏi `#support` Discord kèm log `docker logs tidecloak` |
| A2 | Kết nối Tide MCP (Raziel) vào Claude Code **hoặc** mở TideCloak Quickstart trên docs.tide.org | — | Agent trả lời được câu hỏi tích hợp, hoặc có template Quickstart chạy được | Dùng Quickstart (Plan B chính thức của BTC) |
| A3 | Kích hoạt licence dev, tạo realm `unsellable`, đăng ký web client | A1 | Thấy realm + client trong console | — |
| A4 | Tạo roles `_tide_genome.selfencrypt`, `_tide_genome.selfdecrypt`; tạo 6 user theo bảng Demo accounts; gán role cho `maya` | A3 | Đăng nhập `maya` thấy role trong token | — |
| A5 | Đề cử đúng **3** quorum admin: `admin.company`, `custodian`, `ethics` | A4 | Thử gán role cho user khác → xuất hiện change request chờ duyệt thay vì áp dụng ngay | Ghi lại chính xác hành vi thấy được, báo D để sửa README |
| A6 | Export file adapter config của client, đặt vào chỗ template yêu cầu, gửi B | A3 | B đăng nhập được từ app | — |
| A7 | Ghi lại **mọi** bước/khác biệt so với README §Setup vào `docs/setup-notes.md` | A3–A6 | D có đủ để viết lại Setup | — |

**Gate G1 (mục tiêu ~14:45):** A1–A4 + A6 xong, B đăng nhập được bằng `maya` trong app.

### Luồng B — Frontend

| ID | Việc | Pre | PASS | FAIL → |
|---|---|---|---|---|
| B1 | Khởi tạo app từ template/Quickstart TideCloak (Next.js) vào thư mục `app/` | A2 | `npm run dev` mở được `localhost:3000` | Hỏi MCP; nếu template khác Next.js, giữ template, sửa README |
| B2 | Cắm adapter config, luồng login/logout, hiển thị user + roles hiện tại ở header | A6, B1 | Đăng nhập lần lượt 5 persona, thấy đúng tên/role | — |
| B3 | Trang **My genome** (maya): nút "Seal genome" → encrypt bằng SDK TideCloak → POST ciphertext lên API C; nút "Open" → lấy ciphertext → decrypt → hiện bảng markers | B2, C1 | Seal rồi reload trang, Open ra lại đúng 3 marker | Hỏi MCP cách gọi encrypt/decrypt có tag `genome`; nếu kẹt >30 phút báo cả team |
| B4 | Trang **Admin** (acquirer): nút "Export all genomes" → gọi decrypt trên từng bản ghi → hiện lỗi từ chối rõ ràng (đỏ, "Denied by Tide Fabric") | B3 | Đăng nhập `admin.acquirer`, bấm → thấy denied, không có plaintext | — |
| B5 | Trên trang Admin: nút "Grant myself genome read access" → tạo change request gán role (qua API admin của TideCloak nếu MCP hướng dẫn được) và hiện trạng thái pending | A5, B2 | Thấy "Pending" và request xuất hiện cho các quorum admin | **Fallback §4**: bỏ nút, demo bước này ngay trong TideCloak admin console |
| B6 | Polish tối thiểu: banner "Synthetic data", nav giữa các trang, màu trạng thái | B3–B4 | Nhìn rõ trên video 1080p | Bỏ qua nếu trễ |

**Gate G2 (mục tiêu ~16:00):** D1–D4 chạy end-to-end liên tục 2 lần không lỗi.

### Luồng C — Data/Backend

| ID | Việc | Pre | PASS | FAIL → |
|---|---|---|---|---|
| C1 | API route trong app: `POST /api/genome` (lưu), `GET /api/genome/:id` (trả ciphertext), lưu vào `data/genomes.json` theo Data model README | B1 | `curl` lưu/đọc được bản ghi | — |
| C2 | Seed genome tổng hợp (3 marker như README) dạng JSON hằng số ở client — **không** lưu plaintext lên server | — | grep `data/genomes.json` không thấy `rs0000001` | — |
| C3 | Trang **Database view**: đọc thẳng `data/genomes.json`, in raw | C1 | Thấy trường `genome` là ciphertext | — |
| C4 | `GET /api/export-all`: trả về toàn bộ bản ghi (ciphertext) — để chứng minh "export được file nhưng chỉ là ciphertext" | C1 | Acquirer tải về chỉ thấy ciphertext | — |
| C5 | Hỗ trợ B ở B4/B5; viết `npm run seed` nếu cần dữ liệu cho nhiều participant | C1 | — | — |

### Luồng D — Story & Submit (bắt đầu ngay, không chờ code)

| ID | Việc | Pre | PASS | FAIL → |
|---|---|---|---|---|
| D1 | Viết kịch bản video 2 phút theo 4 phần BTC gợi ý (Possibility → Constraint → Prototype → What changes), map với bước 1–6 README | — | Script đọc to ≤ 2:00 | — |
| D2 | Kiểm tra lại các con số/trích dẫn trong README (23andMe, UK Biobank) bằng cách mở từng link References | — | Mỗi số có link khớp, hoặc đã sửa/xoá | Xoá số không xác minh được |
| D3 | Thu gọn overview ≤ 300 từ (đếm lại) | — | `wc -w` phần overview ≤ 300 | — |
| D4 | Sau G2: sửa bảng **Prototype status**, Setup (từ `docs/setup-notes.md`), xoá các `TODO(team)`, thêm tên thành viên | G2, A7 | Không còn `TODO(team)`; mọi dòng "Implemented" đều có trong video | — |
| D5 | Quay video (OBS/QuickTime), 1080p, nén ≤ 100 MB → `demo.mp4` ở gốc repo | G2 | `ls -lh demo.mp4` < 100M, xem lại thấy rõ bước 4–5 | Nén bằng `ffmpeg -crf 28` |
| D6 | Test setup "clean": người không code clone repo, làm theo README | D4 | Lên được trang login | Ghi lỗi, sửa README |
| D7 | Repo **public**, push, nộp Google Form | D4–D5 | Mở repo ở tab ẩn danh thấy code + video; form xác nhận đã gửi | — |

---

## 3. Lịch theo giờ (giờ VN)

| Giờ | A | B | C | D |
|---|---|---|---|---|
| 13:45–14:45 | A1–A4, A6 | A2 cùng A, B1 | C1, C2 | D1, D2 |
| 14:45 **G1** | Xác nhận maya login được trong app | | | |
| 14:45–16:00 | A5, A7, hỗ trợ B5 | B2–B4 | C3, C4 | D3, chuẩn bị thiết bị quay |
| 16:00 **G2** | Chạy thử D1–D4 end-to-end ×2 | | | |
| 16:00–16:45 | B5 hoặc fallback | B5, B6 | C5, fix bug | Quay thử nháp |
| **16:45 freeze** | Không thêm tính năng | | | |
| 16:45–17:30 | Đóng vai persona khi quay | Lái màn hình | Bấm DB view | D4, D5 |
| 17:30–17:45 | | | | D6 nhanh, D7 |

---

## 4. Fallback đã chốt trước (để không phải họp khi kẹt)

| Nếu… | Thì… |
|---|---|
| MCP không kết nối được sau 15 phút | Dùng TideCloak Quickstart (A2/B1) |
| G1 trễ quá 15:15 | Cắt B6 + C4; D bắt đầu quay phần "Constraint" (slide/voice-over) trước |
| B5 (pending trong app) không xong lúc 16:15 | Demo D5 trực tiếp trong **TideCloak admin console**: acquirer gán role → thấy request chờ → đăng nhập `custodian`, `ethics` reject. Sửa README: "approval shown in TideCloak admin console" |
| Quorum 3 admin không cấu hình được | README ghi đúng những gì chạy được, đưa quorum vào "Planned"; vẫn giữ D2–D4 (Hermetic E2EE là điểm "Why TideCloak") |
| Encrypt/decrypt (B3) kẹt lúc 15:30 | Cả team dồn vào B3 — đây là thứ duy nhất không có fallback |
| Video > 100 MB | `ffmpeg -i in.mov -vcodec libx264 -crf 28 demo.mp4` |

---

## 5. Definition of Done (đo được)

- [ ] Repo public, có code app chạy được + `demo.mp4` < 100 MB
- [ ] Video ≤ 2:00, cho thấy: maya seal/open, DB chỉ có ciphertext, acquirer export bị denied, self-grant pending/rejected
- [ ] README overview ≤ 300 từ, không còn `TODO(team)`, bảng Prototype status khớp video
- [ ] Setup trong README đã được một người khác chạy lại thành công
- [ ] Google Form đã gửi trước 18:00 VN
