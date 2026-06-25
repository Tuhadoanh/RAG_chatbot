"""
Test dataset cho RAGAS evaluation — 15 câu hỏi về báo cáo tài chính SSI 2023.

Cấu trúc mỗi mẫu:
  question      : câu hỏi người dùng gửi vào chatbot
  ground_truth  : câu trả lời tham chiếu (dùng cho context_recall + answer correctness)
  category      : nhóm metric để phân tích sau đánh giá
"""

TEST_DATASET: list[dict] = [
    # ── Nhóm 1: Kết quả kinh doanh tổng hợp ──────────────────────────────────
    {
        "question": "Tổng doanh thu hoạt động của SSI trong năm 2023 là bao nhiêu?",
        "ground_truth": (
            "Tổng doanh thu hoạt động của SSI năm 2023 bao gồm doanh thu từ "
            "hoạt động môi giới, tự doanh chứng khoán, tư vấn tài chính và các "
            "dịch vụ khác, được trình bày trong báo cáo kết quả hoạt động kinh doanh hợp nhất."
        ),
        "category": "revenue",
    },
    {
        "question": "Lợi nhuận trước thuế của SSI năm 2023 là bao nhiêu và thay đổi như thế nào so với năm 2022?",
        "ground_truth": (
            "Lợi nhuận trước thuế của SSI năm 2023 được ghi nhận trong báo cáo "
            "kết quả kinh doanh hợp nhất. Báo cáo so sánh với số liệu năm 2022 "
            "để cho thấy mức tăng/giảm theo tỷ lệ phần trăm."
        ),
        "category": "profit",
    },
    {
        "question": "Lợi nhuận sau thuế thu nhập doanh nghiệp năm 2023 của SSI là bao nhiêu?",
        "ground_truth": (
            "Lợi nhuận sau thuế thu nhập doanh nghiệp của SSI năm 2023 "
            "được trình bày trong báo cáo kết quả hoạt động kinh doanh hợp nhất, "
            "sau khi trừ đi thuế thu nhập doanh nghiệp hiện hành và hoãn lại."
        ),
        "category": "profit",
    },
    {
        "question": "Lợi nhuận sau thuế của cổ đông công ty mẹ năm 2023 là bao nhiêu?",
        "ground_truth": (
            "Lợi nhuận sau thuế của cổ đông công ty mẹ SSI năm 2023 "
            "là phần lợi nhuận phân bổ cho cổ đông sở hữu vốn công ty mẹ, "
            "được thể hiện trong báo cáo kết quả hoạt động kinh doanh hợp nhất."
        ),
        "category": "profit",
    },

    # ── Nhóm 2: Bảng cân đối kế toán ─────────────────────────────────────────
    {
        "question": "Tổng tài sản của SSI tính đến ngày 31/12/2023 là bao nhiêu?",
        "ground_truth": (
            "Tổng tài sản của SSI tính đến cuối năm 2023 (31/12/2023) "
            "bao gồm tài sản ngắn hạn và tài sản dài hạn, được trình bày "
            "trong bảng cân đối kế toán hợp nhất."
        ),
        "category": "balance_sheet",
    },
    {
        "question": "Vốn chủ sở hữu của SSI cuối năm 2023 là bao nhiêu?",
        "ground_truth": (
            "Vốn chủ sở hữu của SSI tại ngày 31/12/2023 bao gồm vốn điều lệ, "
            "thặng dư vốn cổ phần, lợi nhuận sau thuế chưa phân phối và các "
            "quỹ dự trữ, được ghi nhận trong phần vốn chủ sở hữu của bảng cân đối kế toán."
        ),
        "category": "balance_sheet",
    },
    {
        "question": "Tổng nợ phải trả của SSI năm 2023 là bao nhiêu?",
        "ground_truth": (
            "Tổng nợ phải trả của SSI bao gồm nợ ngắn hạn (vay ngân hàng, "
            "trái phiếu phát hành, phải trả khách hàng) và nợ dài hạn, "
            "được trình bày trong bảng cân đối kế toán hợp nhất."
        ),
        "category": "balance_sheet",
    },
    {
        "question": "Tiền và các khoản tương đương tiền của SSI cuối năm 2023 là bao nhiêu?",
        "ground_truth": (
            "Tiền và các khoản tương đương tiền của SSI tại 31/12/2023 "
            "bao gồm tiền mặt, tiền gửi ngân hàng không kỳ hạn và kỳ hạn ngắn, "
            "được ghi nhận trong phần tài sản ngắn hạn của bảng cân đối kế toán."
        ),
        "category": "balance_sheet",
    },

    # ── Nhóm 3: Hoạt động kinh doanh cốt lõi ────────────────────────────────
    {
        "question": "Doanh thu từ hoạt động môi giới chứng khoán của SSI năm 2023 như thế nào?",
        "ground_truth": (
            "Doanh thu từ hoạt động môi giới chứng khoán của SSI năm 2023 "
            "phản ánh phí hoa hồng từ các giao dịch cổ phiếu, trái phiếu và "
            "các sản phẩm phái sinh, là nguồn doanh thu cốt lõi của công ty."
        ),
        "category": "core_business",
    },
    {
        "question": "Kết quả hoạt động tự doanh (đầu tư tài chính) của SSI năm 2023 ra sao?",
        "ground_truth": (
            "Kết quả hoạt động tự doanh của SSI năm 2023 bao gồm lãi/lỗ từ "
            "danh mục đầu tư chứng khoán tự doanh, cổ phiếu và trái phiếu nắm giữ "
            "để giao dịch hoặc sẵn sàng để bán."
        ),
        "category": "core_business",
    },
    {
        "question": "Chi phí hoạt động của SSI năm 2023 là bao nhiêu, các khoản chi phí lớn nhất là gì?",
        "ground_truth": (
            "Chi phí hoạt động của SSI năm 2023 bao gồm chi phí nhân viên, "
            "chi phí thuê văn phòng, chi phí công nghệ thông tin, chi phí quản lý "
            "và các chi phí hoạt động khác, được trình bày trong báo cáo kết quả kinh doanh."
        ),
        "category": "cost",
    },

    # ── Nhóm 4: Dòng tiền và cổ tức ─────────────────────────────────────────
    {
        "question": "Dòng tiền thuần từ hoạt động kinh doanh của SSI năm 2023 là bao nhiêu?",
        "ground_truth": (
            "Dòng tiền thuần từ hoạt động kinh doanh của SSI năm 2023 "
            "phản ánh khả năng tạo tiền mặt từ hoạt động chính, "
            "được trình bày trong báo cáo lưu chuyển tiền tệ hợp nhất."
        ),
        "category": "cashflow",
    },
    {
        "question": "SSI có chi trả cổ tức năm 2023 không? Tỷ lệ cổ tức là bao nhiêu?",
        "ground_truth": (
            "Thông tin về cổ tức của SSI năm 2023 bao gồm tỷ lệ chi trả, "
            "hình thức chi trả (tiền mặt hoặc cổ phiếu) và tổng số tiền "
            "cổ tức đã phân phối cho cổ đông, được công bố trong thuyết minh báo cáo tài chính."
        ),
        "category": "dividend",
    },

    # ── Nhóm 5: Chỉ số tài chính ─────────────────────────────────────────────
    {
        "question": "Chỉ số ROE (lợi nhuận trên vốn chủ sở hữu) của SSI năm 2023 là bao nhiêu?",
        "ground_truth": (
            "ROE của SSI năm 2023 được tính bằng lợi nhuận sau thuế chia cho "
            "vốn chủ sở hữu bình quân, phản ánh hiệu quả sử dụng vốn. "
            "Chỉ số này thường được trình bày trong phần phân tích tài chính của báo cáo thường niên."
        ),
        "category": "ratio",
    },
    {
        "question": "Vốn điều lệ của SSI tính đến cuối năm 2023 là bao nhiêu?",
        "ground_truth": (
            "Vốn điều lệ của SSI tính đến ngày 31/12/2023 là số vốn đã được "
            "đăng ký và thực góp của các cổ đông, được ghi nhận trong bảng cân đối "
            "kế toán và thuyết minh báo cáo tài chính."
        ),
        "category": "balance_sheet",
    },
]
