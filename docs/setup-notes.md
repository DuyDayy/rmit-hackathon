# TideCloak setup notes (Luồng A)

Nguồn cho phần Setup của README. Ghi đúng những gì đã chạy thật.

## 1. TideCloak dev container

Image `tideorg/tidecloak-dev:latest` (build 2026-10-19):

```bash
docker run --name tidecloak -d \
  -v "$PWD/.tidecloak-data:/opt/keycloak/data/h2" \
  -p 8080:8080 \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin \
  -e KC_BOOTSTRAP_ADMIN_PASSWORD=password \
  tideorg/tidecloak-dev:latest
```

Mật khẩu là `password` vì script init của template mặc định dùng giá trị đó (`KC_PASSWORD`). Chỉ dùng cho dev local. `.tidecloak-data/` đã nằm trong `.gitignore`.

## 2. App template và thay đổi so với template

Code app (`app/src/`, Next.js 14 + `@tidecloak/nextjs` 0.14.40) là của luồng B/C. Từ template `@tidecloak/create-nextjs@0.14.33` chỉ giữ thư mục `app/init/` (script provisioning, chạy bằng `npm run init`).

- `app/init/.env.example`: realm `unsellable`, client `unsellable-web`, `FIRST_ADMIN_USERNAME=admin.company`.
- `app/init/realm.json`: thêm realm roles `_tide_genome.selfencrypt` và `_tide_genome.selfdecrypt`. Hai role này **không** nằm trong default role.
- `app/init/tcinit.sh`: lúc realm còn ở firstAdmin mode (change request tự commit), script tạo đủ 6 persona và gán genome roles cho `maya`, **từng role một**. Khi gán 2 role trong cùng một request, server trả 409 và chỉ commit role đầu tiên. First admin là `admin.company`.

## 3. Provisioning

```bash
cd app && bash init/tcinit.sh
```

Script in ra link "ACTION REQUIRED". Mở link đó và enroll Tide account cho `admin.company`. Script tự chạy tiếp, ký IdP settings, cấp `tide-realm-admin`, chuyển realm sang multiAdmin rồi ghi `app/tidecloak.json`.

### Lỗi tạm thời từ Fabric của Tide (retry là được)

- `setUpTideRealm` → HTTP 500 `TIDE-IDPEXT-VENDOR-KEYGEN_FAILED` (log: `Midgard.FinalizeWallet ... 500`). Bị 3 lần liên tiếp, kể cả với script gốc chưa sửa; lần thứ 4 thì chạy được. Cách xử lý: xoá realm (`DELETE /admin/realms/unsellable`) rồi chạy lại script.
- Approve change request → HTTP 500 (`Midgard.SignModel: AttestationUnit:1`). Vòng drain của script tự retry, cuối cùng cả 6 CREATE_USER đều APPROVED.

## 4. Trạng thái realm `unsellable` (đã kiểm tra qua admin API)

| User | Realm roles | Enrolled Tide |
|---|---|---|
| `admin.company` | default | đang chờ (human gate) |
| `maya` | default + `_tide_genome.selfencrypt` + `_tide_genome.selfdecrypt` | chưa |
| `admin.acquirer` | default (`_tide_message.*`, `appUser`) — **không có genome role** | chưa |
| `lee`, `custodian`, `ethics` | default | chưa |

## 5. Còn lại

1. Enroll `admin.company` (đang chặn script init).
2. Enroll 5 persona còn lại (link do admin API mint: `POST /admin/realms/unsellable/tideAdminResources/get-required-action-link?userId=<id>&lifespan=3600`, body `["link-tide-account-action"]`).
3. Thêm `custodian` và `ethics` làm `tide-realm-admin` qua governance trong tide-console (`http://localhost:8080/realms/unsellable/tide-console/`). Sau đó kiểm tra: self-grant `_tide_genome.selfdecrypt` của `admin.acquirer` phải ra **PENDING**.
4. Gửi `app/tidecloak.json` cho B.
