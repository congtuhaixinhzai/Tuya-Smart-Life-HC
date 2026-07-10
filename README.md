# Tuya Smart Life HC

Tích hợp tùy chỉnh cho Home Assistant: đăng nhập bằng tài khoản Tuya thường, lấy thiết bị từ mobile API, rồi điều khiển local qua LAN khi thiết bị hỗ trợ Tuya local protocol.

Không cần dự án Tuya IoT Cloud. Không cần nhập `app_id`, `app_secret`, certificate fingerprint hoặc native signing key.

## Cài đặt nhanh

Mở kho mã này trong HACS:

[![Mở kho mã trong HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=congtuhaixinhzai&repository=Tuya-Smart-Life-HC&category=integration)

Sau khi tải xong và restart Home Assistant, mở màn hình cấu hình:

[![Bắt đầu thiết lập integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tuya_smart_hc)

## Thiết lập

1. Vào **Settings -> Devices & services**.
2. Bấm **Add integration**.
3. Tìm **Tuya Smart Life HC**.
4. Chọn **Ứng dụng** là **Tuya** hoặc **Smart Life**.
5. Nhập email/số điện thoại Tuya và mật khẩu.
6. Chọn các nhà muốn đồng bộ, hoặc để trống nếu chưa muốn tải thiết bị.

Với email, integration không hỏi mã vùng. Với số điện thoại Việt Nam, integration vẫn dùng mặc định `84` nội bộ.

## Tài liệu

- [Cài đặt, đăng nhập và cập nhật](docs/setup.md)
- [Cơ chế điều khiển local](docs/local-control.md)
- [Thiết bị công tắc, DPS và cảm biến](docs/devices-switch.md)
- [Lịch và hẹn tắt thiết bị](docs/devices-schedule.md)
- [MQTT cloud tự suy ra thông tin đăng nhập](docs/mqtt-auto-credentials.md)
- [Khóa Wi-Fi và mở khóa](docs/devices-lock.md)
- [Xử lý sự cố](docs/troubleshooting.md)
- [Reverse engineering, MITM, signing, crypto](docs/reverse-engineering.md)
- Bản đồ API Android Tuya Smart (docs/tuya-smart-android-api-findings.md)

## Hướng dẫn sử dụng Điều hòa hồng ngoại (IR) và Sao lưu

Phiên bản mới nhất đã được nâng cấp mạnh mẽ để hỗ trợ điều hòa hồng ngoại (IR) qua Cloud API và loại bỏ hoàn toàn các thiết bị rác tự sinh.

### 1. Thêm Điều hòa IR thủ công
- Đi tới **Cài đặt -> Thiết bị & Dịch vụ** trong Home Assistant.
- Tìm thẻ tích hợp **Tuya Smart Life HC**, bấm nút **Cấu hình** (Configure).
- Chọn **Thêm Điều hòa IR** và làm theo hướng dẫn:
  - Chọn Bộ phát hồng ngoại (IR Hub).
  - Chọn thiết bị máy lạnh tương ứng.
  - Đặt tên hiển thị.

### 2. Xóa các thiết bị IR rác tự sinh
Từ phiên bản này, hệ thống sẽ **KHÔNG BAO GIỜ** tự động nhận diện và sinh ra các thiết bị IR rác nữa.
Nếu hệ thống của bạn vẫn còn các thiết bị cũ tự sinh:
- Vào tab **Thiết bị**.
- Chọn thiết bị rác, bấm vào icon hình cái bút (hoặc dấu 3 chấm).
- Chọn **Xóa**. Hệ thống sẽ xóa ngay lập tức mà không báo lỗi.

### 3. Tự động Sao lưu và Khôi phục
Hệ thống tích hợp sẵn tính năng tự động sao lưu cấu hình các điều hòa mà bạn đã thêm thủ công.
- **Tự động lưu**: Bất cứ khi nào bạn Thêm/Sửa/Xóa điều hòa, danh sách sẽ được tự động lưu ra file `/config/tuya_smart_hc_climates.json`.
- **Khôi phục**: Nếu bạn vô tình gỡ cài đặt Tích hợp và cài lại, chỉ cần bấm **Cấu hình** -> Chọn **Khôi phục từ bản sao lưu**. Toàn bộ điều hòa sẽ được tự động thiết lập lại như cũ!

## Ghi chú nhanh

- Home Assistant nên ở cùng LAN/broadcast domain với thiết bị hoặc hub Tuya.
- Thiết bị Wi-Fi/root có IP local sẽ có cảm biến IP local.
- Chỉ hub mới hiển thị online/offline cloud.
- MQTT không cần nhập thủ công; tích hợp tự suy ra từ phiên đăng nhập mobile nếu Tuya trả đủ dữ liệu.
- IR được thiết lập độc lập và lưu trữ thông tin nội bộ an toàn qua cơ chế sao lưu mới.

APK, source decompile, capture thật, thông tin đăng nhập, session token và local key không được commit vào kho mã.
