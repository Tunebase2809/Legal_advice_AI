class TaxCalculator:
    def __init__(self):
        self.tax_rates = {
            # Nhóm 1: Phân phối, cung cấp hàng hóa (GTGT 1%, TNCN 1%)
            "ban_buon_ban_le": {"gtgt": 0.01, "tncn": 0.01},
            "ban_le_thuoc_my_pham": {"gtgt": 0.01, "tncn": 0.01},
            
            # Nhóm 2: Dịch vụ, xây dựng không bao thầu (GTGT 5%, TNCN 5%)
            "nha_hang_quan_an_cafe": {"gtgt": 0.05, "tncn": 0.05},
            "dich_vu_lam_dep_spa": {"gtgt": 0.05, "tncn": 0.05},
            "dich_vu_sua_chua": {"gtgt": 0.05, "tncn": 0.05},
            "dich_vu_tu_van": {"gtgt": 0.05, "tncn": 0.05},
            "xay_dung_khong_bao_thau": {"gtgt": 0.05, "tncn": 0.05},
            
            # Nhóm 3: Sản xuất, vận tải, dịch vụ có gắn hàng hóa (GTGT 3%, TNCN 2%)
            "san_xuat_gia_cong": {"gtgt": 0.03, "tncn": 0.02},
            "van_tai_hang_hoa_hanh_khach": {"gtgt": 0.03, "tncn": 0.02},
            "xay_dung_co_bao_thau": {"gtgt": 0.03, "tncn": 0.02},
            
            # Nhóm 4: Hoạt động kinh doanh khác (GTGT 2%, TNCN 2%)
            "khai_thac_khoang_san": {"gtgt": 0.02, "tncn": 0.02},
            "san_xuat_ttdb": {"gtgt": 0.02, "tncn": 0.02},
            "hoat_dong_khac": {"gtgt": 0.02, "tncn": 0.02},
            
            # Nhóm đặc thù: Thuế suất (GTGT 5%, TNCN 5%)
            "cho_thue_tai_san_dai_ly": {"gtgt": 0.05, "tncn": 0.05},
            "dich_vu_noi_dung_so": {"gtgt": 0.05, "tncn": 0.05}
        }
        
        self.category_metadata = {
            "ban_buon_ban_le": {
                "name": "Bán buôn, bán lẻ hàng hóa",
                "group_name": "Nhóm 1: Phân phối, cung cấp hàng hóa",
                "full_name": "Nhóm 1: Phân phối, cung cấp hàng hóa (Bán buôn, bán lẻ)"
            },
            "ban_le_thuoc_my_pham": {
                "name": "Bán lẻ thuốc, dụng cụ y tế, mỹ phẩm",
                "group_name": "Nhóm 1: Phân phối, cung cấp hàng hóa",
                "full_name": "Nhóm 1: Phân phối, cung cấp hàng hóa (Bán lẻ thuốc, mỹ phẩm)"
            },
            "nha_hang_quan_an_cafe": {
                "name": "Dịch vụ lưu trú, nhà hàng, quán ăn, quán cafe",
                "group_name": "Nhóm 2: Dịch vụ",
                "full_name": "Nhóm 2: Dịch vụ (Nhà hàng, quán ăn, kinh doanh cafe)"
            },
            "dich_vu_lam_dep_spa": {
                "name": "Dịch vụ làm đẹp, spa, thẩm mỹ",
                "group_name": "Nhóm 2: Dịch vụ",
                "full_name": "Nhóm 2: Dịch vụ (Làm đẹp, spa, thẩm mỹ)"
            },
            "dich_vu_sua_chua": {
                "name": "Dịch vụ sửa chữa máy móc, thiết bị, xe cộ",
                "group_name": "Nhóm 2: Dịch vụ",
                "full_name": "Nhóm 2: Dịch vụ (Sửa chữa máy móc, thiết bị, xe cộ)"
            },
            "dich_vu_tu_van": {
                "name": "Dịch vụ tư vấn pháp lý, kế toán, thiết kế",
                "group_name": "Nhóm 2: Dịch vụ",
                "full_name": "Nhóm 2: Dịch vụ (Tư vấn pháp lý, kế toán, thiết kế)"
            },
            "xay_dung_khong_bao_thau": {
                "name": "Xây dựng không bao thầu nguyên vật liệu",
                "group_name": "Nhóm 2: Dịch vụ",
                "full_name": "Nhóm 2: Xây dựng không bao thầu nguyên vật liệu"
            },
            "san_xuat_gia_cong": {
                "name": "Sản xuất, gia công sản phẩm hàng hóa",
                "group_name": "Nhóm 3: Sản xuất, vận tải, xây dựng",
                "full_name": "Nhóm 3: Sản xuất, gia công sản phẩm hàng hóa"
            },
            "van_tai_hang_hoa_hanh_khach": {
                "name": "Vận tải hàng hóa, vận tải hành khách",
                "group_name": "Nhóm 3: Sản xuất, vận tải, xây dựng",
                "full_name": "Nhóm 3: Vận tải hàng hóa, vận tải hành khách"
            },
            "xay_dung_co_bao_thau": {
                "name": "Xây dựng có bao thầu nguyên vật liệu",
                "group_name": "Nhóm 3: Sản xuất, vận tải, xây dựng",
                "full_name": "Nhóm 3: Xây dựng có bao thầu nguyên vật liệu"
            },
            "khai_thac_khoang_san": {
                "name": "Khai thác khoáng sản, tài nguyên",
                "group_name": "Nhóm 4: Hoạt động sản xuất, kinh doanh khác",
                "full_name": "Nhóm 4: Khai thác khoáng sản, tài nguyên"
            },
            "san_xuat_ttdb": {
                "name": "Sản xuất hàng hóa thuộc diện chịu thuế TTĐB",
                "group_name": "Nhóm 4: Hoạt động sản xuất, kinh doanh khác",
                "full_name": "Nhóm 4: Sản xuất hàng hóa thuộc diện chịu thuế TTĐB"
            },
            "hoat_dong_khac": {
                "name": "Hoạt động sản xuất, kinh doanh khác",
                "group_name": "Nhóm 4: Hoạt động sản xuất, kinh doanh khác",
                "full_name": "Nhóm 4: Hoạt động sản xuất, kinh doanh khác"
            },
            "cho_thue_tai_san_dai_ly": {
                "name": "Cho thuê tài sản; Đại lý bảo hiểm, xổ số, đa cấp",
                "group_name": "Nhóm đặc thù",
                "full_name": "Nhóm đặc thù: Cho thuê tài sản; Đại lý bảo hiểm, xổ số, đa cấp"
            },
            "dich_vu_noi_dung_so": {
                "name": "Dịch vụ nội dung thông tin số, quảng cáo số",
                "group_name": "Nhóm đặc thù",
                "full_name": "Nhóm đặc thù: Dịch vụ nội dung thông tin số, quảng cáo số"
            }
        }
        self.category_names = {k: v["full_name"] for k, v in self.category_metadata.items()}

        
        # Các mốc doanh thu và thuế suất định mức (NĐ 141/2026/NĐ-CP & Luật Thuế TNCN 109/2025/QH15)
        self.revenue_milestones = {
            "exemption": 1000000000,          # Doanh thu miễn thuế (1 tỷ/năm)
            "net_level_1": 3000000000,         # Mốc tính thuế lũy tiến mức 1 (3 tỷ/năm)
            "net_level_2": 50000000000         # Mốc tính thuế lũy tiến mức 2 (50 tỷ/năm)
        }
        
        self.tncn_rates_net = {
            "level_1": 0.15,                   # 15% cho doanh thu đến 3 tỷ
            "level_2": 0.17,                   # 17% cho doanh thu từ trên 3 tỷ đến 50 tỷ
            "level_3": 0.20                    # 20% cho doanh thu trên 50 tỷ
        }

    def calculate_tax(self, revenue: float, category: str, method: str = "doanh_thu", expenses: float = 0):
        """
        Tính thuế cho hộ kinh doanh dựa trên công thức cứng.
        Nếu người dùng không cung cấp thông tin ngành nghề, mặc định chọn 'Nhóm 4: Hoạt động sản xuất, kinh doanh khác' và thông báo cho người dùng biết để bổ sung.
        Quy định mới (2026 - NĐ 141): Doanh thu <= 1 tỷ/năm được miễn thuế.
        Với doanh thu > 1 tỷ: 
        - Thuế GTGT tính trên TOÀN BỘ doanh thu.
        - Thuế TNCN tính theo một trong hai phương pháp:
          + Theo doanh thu: Tính trên phần doanh thu vượt 1 tỷ (Mặc định).
          + Theo thu nhập tính thuế: (Doanh thu - Chi phí) x thuế suất.
        """
        exemption_limit = self.revenue_milestones["exemption"]
        if revenue <= exemption_limit:
            return {
                "is_taxable": False,
                "reason": f"Doanh thu từ {exemption_limit/1000000000:.0f} tỷ VNĐ/năm trở xuống, được miễn thuế GTGT và TNCN theo quy định mới (NĐ 141/2026/NĐ-CP).",
                "tax_gtgt": 0,
                "tax_tncn": 0,
                "total_tax": 0
            }
            
        if not category or category not in self.tax_rates:
            category = "hoat_dong_khac"
            
        rate = self.tax_rates[category]
        cat_name = self.category_names.get(category, "Nhóm 4: Hoạt động sản xuất, kinh doanh khác")
        
        # Phần doanh thu tính thuế GTGT (luôn tính trên toàn bộ doanh thu)
        taxable_revenue_gtgt = revenue
        tax_gtgt = taxable_revenue_gtgt * rate["gtgt"]
        
        if method == "thu_nhap":
            # Tính theo Thu nhập tính thuế (Điều 4, NĐ 68/2026 và Khoản 2 Điều 7 Luật Thuế TNCN 109/2025/QH15)
            taxable_income = max(0, revenue - expenses)
            
            # Thuế suất TNCN áp dụng theo phương pháp thu nhập tính thuế (dựa theo doanh thu năm)
            if revenue <= self.revenue_milestones["net_level_1"]:
                tncn_rate_net = self.tncn_rates_net["level_1"]
            elif revenue <= self.revenue_milestones["net_level_2"]:
                tncn_rate_net = self.tncn_rates_net["level_2"]
            else:
                tncn_rate_net = self.tncn_rates_net["level_3"]
                
            tax_tncn = taxable_income * tncn_rate_net
            
            return {
                "is_taxable": True,
                "revenue": revenue,
                "taxable_revenue_gtgt": taxable_revenue_gtgt,
                "taxable_income": taxable_income,
                "category": cat_name,
                "tax_gtgt": tax_gtgt,
                "tax_tncn": tax_tncn,
                "total_tax": tax_gtgt + tax_tncn,
                "explanation": f"- Ngành nghề: {cat_name}\n- Phương pháp: Tính theo Thu nhập tính thuế\n- Doanh thu {revenue:,.0f} VNĐ, Chi phí hợp lý: {expenses:,.0f} VNĐ\n  • Thuế GTGT tính trên toàn bộ doanh thu (Tỷ lệ: {rate['gtgt']*100}%).\n  • Thuế TNCN tính trên Thu nhập tính thuế = Doanh thu - Chi phí = {taxable_income:,.0f} VNĐ (Tỷ lệ: {tncn_rate_net*100}%)."
            }
        else:
            # Phương pháp tính theo doanh thu
            taxable_revenue_tncn = revenue - self.revenue_milestones["exemption"]
            tax_tncn = taxable_revenue_tncn * rate["tncn"]
            
            return {
                "is_taxable": True,
                "revenue": revenue,
                "taxable_revenue_gtgt": taxable_revenue_gtgt,
                "taxable_revenue_tncn": taxable_revenue_tncn,
                "category": cat_name,
                "tax_gtgt": tax_gtgt,
                "tax_tncn": tax_tncn,
                "total_tax": tax_gtgt + tax_tncn,
                "explanation": f"- Ngành nghề: {cat_name}\n- Phương pháp: Tính theo Doanh thu\n- Doanh thu {revenue:,.0f} VNĐ\n  • Thuế GTGT tính trên toàn bộ doanh thu (Tỷ lệ: {rate['gtgt']*100}%).\n  • Thuế TNCN tính trên phần vượt {self.revenue_milestones['exemption']/1000000000:.0f} tỷ (tức là {taxable_revenue_tncn:,.0f} VNĐ, Tỷ lệ: {rate['tncn']*100}%)."
            }
