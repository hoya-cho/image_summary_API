# 이미지 요약 이벤트 프로젝트

## 프로젝트 구조

```
image_summary_event/
├── business_server/                # 비즈니스 로직 및 API 서버
│   ├── app/
│   ├── Dockerfile
│   └── requirements.txt
├── model_servers/                  # AI 모델 서버 모음
│   ├── image_captioning_server/    # 이미지 캡셔닝(설명 생성) 서버
│   ├── object_detection_server/    # 객체 탐지 서버
│   └── text_summarization_server/  # 텍스트 요약(생성) 서버
├── tests/                          # 테스트 클라이언트 및 샘플 이미지
│   ├── test_client.py
│   └── sample_images/
├── docker-compose.yml              # 전체 서비스 오케스트레이션
└── .env                            # 환경 변수 파일
```

---

## Docker Compose로 전체 서비스 빌드/실행/삭제

### 1. 빌드
```bash
docker compose build
```

### 2. 실행 (백그라운드)
```bash
docker compose up -d
```

### 3. 중지 및 컨테이너+볼륨 삭제 (데이터 완전 삭제)
```bash
docker compose down -v
```
- `-v` 옵션을 사용하면 MongoDB 등 모든 데이터 볼륨이 완전히 삭제됩니다.

---

## 테스트 클라이언트 및 샘플 이미지

- 테스트 클라이언트:  
  `tests/test_client.py`
- 샘플 이미지:  
  `tests/sample_images/` 폴더에 여러 PNG 파일이 준비되어 있습니다.

### 테스트 방법

1. **서버가 실행 중인지 확인**  
   (docker compose로 전체 서비스가 실행 중이어야 함)

2. **테스트 클라이언트 실행**
   ```bash
   cd tests
   python test_client.py
   ```
   - 이 스크립트는 `sample_images/` 폴더의 이미지를 자동으로 찾아서,  
     비즈니스 서버의 `/api/upload_image/` 엔드포인트로 업로드합니다.
   - 업로드 결과(성공/실패, 메시지, request_id 등)가 로그로 출력됩니다.

3. **샘플 이미지**
   - `sample_images/` 폴더에는 다양한 PNG 파일이 포함되어 있습니다.
   - 각 파일명에서 고객 ID를 추출하여 테스트 요청에 사용합니다.

---

## 기타

- 환경 변수는 `.env` 파일에서 관리합니다.
- 각 모델 서버는 FastAPI 기반 REST API로 동작합니다.
- MongoDB 데이터는 `docker compose down -v`로 완전히 삭제할 수 있습니다.

---

