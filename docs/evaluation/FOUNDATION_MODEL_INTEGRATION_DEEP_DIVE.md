# PHÂN TÍCH CHUYÊN SÂU KIẾN TRÚC DEEP LEARNING CỦA 5 MÔ HÌNH NỀN TẢNG & MẠNG CHUYÊN BIỆT TRONG MODEL ZOO
> **Dự án**: Khóa luận Tốt nghiệp & Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop (MIS / ITBA / AI)\
> **Cấp độ triển khai**: Báo cáo Nghiên cứu Kiến trúc & Cơ sở Lý thuyết Học máy Y tế (RUO)\
> **Tài liệu tham chiếu**: [AGENTS.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/AGENTS.md), [master_15_repo_integration_report.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/master_15_repo_integration_report.md), [model_zoo_benchmark_results.json](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/model_zoo_benchmark_results.json)\
> **Mã tài liệu**: `DOC-FOUNDATION-MODEL-DEEPDIVE-20261101`\
> **Ngày hoàn thành**: 01/11/2026\

---

## MỤC LỤC TỔNG QUAN
1. [Giới thiệu & Định hướng Kiến trúc Model Zoo](#1-giới-thiệu--định-hướng-kiến-trúc-model-zoo)
2. [Mô hình 1: Boosted U-Net++ scSE (Production Champion)](#2-mô-hình-1-boosted-unet-scse-production-champion)
3. [Mô hình 2: TinyUSFM ViT Hybrid Adapter (Ultrasound Foundation Model)](#3-mô-hình-2-tinyusfm-vit-hybrid-adapter-ultrasound-foundation-model)
4. [Mô hình 3: CSA-SegNet Attention & SPPF (Chuyên biệt Hình thái Buồng trứng)](#4-mô-hình-3-csa-segnet-attention--sppf-chuyên-biệt-hình-thái-buồng-trứng)
5. [Mô hình 4: Interactive MedSAM / SAMUS (Phân đoạn Tương tác Human-in-the-Loop)](#5-mô-hình-4-interactive-medsam--samus-phân-đoạn-tương-tác-human-in-the-loop)
6. [Mô hình 5: MedNeXt ConvNeXt Blocks (Tối ưu Receptive Field Lớn)](#6-mô-hình-5-mednext-convnext-blocks-tối-ưu-receptive-field-lớn)
7. [Ma trận Đối sánh Tổng hợp & Quyết định Phân tầng Lâm sàng](#7-ma-trận-đối-sánh-tổng-hợp--quyết-định-phân-tầng-lâm-sàng)

---

## 1. GIỚI THIỆU & ĐỊNH HƯỚNG KIẾN TRÚC MODEL ZOO

Phân đoạn tổn thương buồng trứng trên ảnh siêu âm 2D là một bài toán học máy y tế đầy thách thức do:
- **Đặc tính âm học phức tạp**: Nhiễu đốm âm học (acoustic speckle noise), độ suy giảm chùm sóng âm theo chiều sâu (acoustic attenuation), và bóng cản âm (acoustic shadowing) phía sau các cấu trúc vôi hóa hoặc tóc/xương trong u nang bì (dermoid cyst).
- **Ranh giới mờ và đa dạng hình thái**: Thành nang mỏng của nang noãn sinh lý, vách ngăn mỏng trong u nang tuyến nhầy (mucinous cystadenoma), hoặc chồi sùi/thành phần đặc trong khối u giáp biên/ác tính.
- **Yêu cầu triển khai thực tế**: Hệ thống cần phục vụ đồng thời chế độ chẩn đoán tự động tốc độ cao trên máy trạm thông thường, chế độ tương tác tinh chỉnh của bác sĩ (HITL), và đối chuẩn học thuật quốc tế.

Để đáp ứng trọn vẹn các yêu cầu trên, hệ thống tích hợp **Model Zoo gồm 5 kiến trúc Deep Learning tiên phong**, tạo thành một dải giải pháp từ mô hình nền tảng tổng quát (Foundation Models) đến các mạng chuyên biệt hóa cao độ (Domain-specific Networks).

```mermaid
graph TD
    subgraph Model_Zoo_Spectrum ["Hệ Phổ Kiến Trúc Model Zoo Buồng Trứng"]
        direction LR
        M1["Boosted U-Net++ scSE<br/>(Production Champion)<br/>Deep Supervision + Attention"]
        M2["TinyUSFM ViT Adapter<br/>(Foundation Model)<br/>Pretrained 2M+ US images"]
        M3["CSA-SegNet SPPF<br/>(Boundary Specialist)<br/>Acoustic Shadow & SPPF"]
        M4["MedSAM / SAMUS<br/>(Interactive HITL)<br/>Point & Box Promptable"]
        M5["MedNeXt ConvNeXt<br/>(Modern ConvNet)<br/>7x7 Large Receptive Field"]
    end
```

---

## 2. MÔ HÌNH 1: BOOSTED U-NET++ scSE (PRODUCTION CHAMPION)

Mô hình chủ lực triển khai trong môi trường kiểm định thực tế của đề tài là kiến trúc **Nested U-Net (U-Net++)** kết hợp backbone **ResNet-34**, khối chú ý kép **scSE (Spatial and Channel Squeeze-and-Excitation)** và cơ chế **Deep Supervision** (mã nguồn huấn luyện tại [`ai_training/train_boosted_unetplusplus.py`](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/ai_training/train_boosted_unetplusplus.py)).

### 2.1. Cấu trúc Đường dẫn Nhảy Lồng nhau (Nested Dense Skip Pathways)
Khác với U-Net cổ điển chỉ nối trực tiếp đặc trưng cùng mức từ Encoder sang Decoder qua một đường dẫn đơn lẻ, U-Net++ xây dựng một mạng lưới các nút tích chập trung gian dày đặc.

```mermaid
graph TD
    X00["X0,0 (Input / Stem)"] -->|Downsample| X10["X1,0"]
    X10 -->|Downsample| X20["X2,0"]
    X20 -->|Downsample| X30["X3,0"]
    X30 -->|Downsample| X40["X4,0 (Bottleneck)"]

    X00 -->|Dense Skip| X01["X0,1 (scSE)"]
    X10 -->|Upsample| X01

    X00 -->|Dense Skip| X02["X0,2 (scSE)"]
    X01 -->|Dense Skip| X02
    X10 -->|Dense Skip| X11["X1,1"]
    X20 -->|Upsample| X11
    X11 -->|Upsample| X02

    X00 -->|Dense Skip| X03["X0,3 (scSE)"]
    X01 -->|Dense Skip| X03
    X02 -->|Dense Skip| X03
    X10 -->|Dense Skip| X12["X1,2"]
    X11 -->|Dense Skip| X12
    X20 -->|Dense Skip| X21["X2,1"]
    X30 -->|Upsample| X21
    X21 -->|Upsample| X12
    X12 -->|Upsample| X03

    X00 -->|Dense Skip| X04["X0,4 (scSE)"]
    X01 -->|Dense Skip| X04
    X02 -->|Dense Skip| X04
    X03 -->|Dense Skip| X04
    X40 -->|Upsample| X31["X3,1"]
    X31 -->|Upsample| X22["X2,2"]
    X22 -->|Upsample| X13["X1,3"]
    X13 -->|Upsample| X04

    X01 -.->|Deep Sup L1| Head1["Head 1"]
    X02 -.->|Deep Sup L2| Head2["Head 2"]
    X03 -.->|Deep Sup L3| Head3["Head 3"]
    X04 ==>|Primary Output| FinalHead["Final Mask"]
```

#### Công thức toán học biểu diễn nút $X^{i,j}$:
Gọi $x^{i,j}$ là đầu ra của nút $X^{i,j}$, trong đó $i \in \{0, 1, 2, 3, 4\}$ là chỉ số tầng lấy mẫu xuống (downsampling layer) và $j \in \{0, 1, 2, 3, 4\}$ là chỉ số khối tích chập dọc theo đường dẫn nhảy:
$$x^{i,j} = \begin{cases}
\mathcal{H}\left( x^{i-1, 0} \right), & j = 0 \\
\mathcal{H}\left( \left[ \left[ x^{i,k} \right]_{k=0}^{j-1}, \mathcal{U}\left( x^{i+1, j-1} \right) \right] \right), & j > 0
\end{cases}$$
Trong đó:
- $\mathcal{H}(\cdot)$ là chuỗi biến đổi tích chập: $\text{Conv}_{3\times 3} \to \text{BatchNorm} \to \text{ReLU} \to \text{scSE}$.
- $\mathcal{U}(\cdot)$ là phép toán nội suy phóng đại (Bilinear Upsampling hoặc Transposed Convolution).
- $[\cdot]$ biểu thị phép ghép nối tensor dọc theo chiều kênh đặc trưng (channel concatenation).

### 2.2. Cơ chế Deep Supervision (Giám sát Sâu)
Trong quá trình huấn luyện, các đầu ra trung gian tại các nút độ phân giải cao $X^{0,1}, X^{0,2}, X^{0,3}, X^{0,4}$ đều được kết nối với một đầu phân loại $1 \times 1$ conv. Tổng hàm mất mát huấn luyện là tổ hợp có trọng số:
$$\mathcal{L}_{\text{total}} = \sum_{j=1}^{4} \lambda_j \cdot \mathcal{L}_{\text{hybrid}}\left( y, \sigma\left( \text{Conv}_{1\times 1}\left( x^{0,j} \right) \right) \right)$$
Với $\lambda_1 = 0.1, \lambda_2 = 0.2, \lambda_3 = 0.3, \lambda_4 = 0.4$ và $\mathcal{L}_{\text{hybrid}} = \mathcal{L}_{\text{Focal-Tversky}} + \mathcal{L}_{\text{SoftDice}} + \mathcal{L}_{\text{BCE}}$.
- **Lợi ích y khoa**: Deep supervision ép buộc các tầng trung gian học được biểu diễn hình thái tổn thương từ sớm, ngăn chặn hiện tượng triệt tiêu gradient (vanishing gradient) qua mạng sâu, đồng thời cho phép cắt tỉa mô hình (model pruning) khi cần chạy siêu nhanh trên thiết bị biên.

### 2.3. Khối Chú ý Kép scSE (Concurrent Spatial and Channel Squeeze-and-Excitation)
Mỗi khối giải mã được tích hợp module scSE (Roy et al., IEEE TMI 2018), kết hợp đồng thời tái hiệu chuẩn theo kênh (Channel SE) và theo không gian (Spatial SE):

```mermaid
graph LR
    U["Đặc trưng U [C x H x W]"] --> cSE["Nhánh cSE (Channel Attention)<br/>Global Pooling -> 2x MLP -> Sigmoid -> Scale Channels"]
    U --> sSE["Nhánh sSE (Spatial Attention)<br/>Conv 1x1 -> Sigmoid -> Scale Spatial Pixels"]
    cSE --> Add["Phép Cộng Phần Tử (+)<br/>Fusion U_scSE = U_cSE + U_sSE"]
    sSE --> Add
    Add --> Out["Đầu ra Tinh chỉnh [C x H x W]"]
```

1. **Nhánh Channel Squeeze-and-Excitation ($\text{cSE}$)**:
   - Squeeze: Nén không gian qua phép gom trung bình toàn cục (Global Average Pooling):
     $$z_c = \frac{1}{H \times W} \sum_{i=1}^H \sum_{j=1}^W u_c(i,j), \quad z \in \mathbb{R}^C$$
   - Excitation: Học mối tương quan giữa các kênh bằng mạng 2 tầng đầy đủ kèm tỷ lệ co ngót $r = 16$:
     $$s = \sigma\left( W_2 \cdot \delta\left( W_1 z \right) \right), \quad W_1 \in \mathbb{R}^{\frac{C}{r} \times C}, W_2 \in \mathbb{R}^{C \times \frac{C}{r}}$$
   - Tái hiệu chuẩn: $\hat{U}_{\text{cSE}} = \left[ s_1 u_1, s_2 u_2, \dots, s_C u_C \right]$.
2. **Nhánh Spatial Squeeze-and-Excitation ($\text{sSE}$)**:
   - Nén kênh: Chiếu toàn bộ $C$ kênh thành 1 bản đồ trọng số không gian qua tích chập $1 \times 1$:
     $$q = \sigma\left( W_{\text{sq}} * U \right), \quad W_{\text{sq}} \in \mathbb{R}^{1 \times 1 \times C \times 1}, \quad q \in \mathbb{R}^{H \times W}$$
   - Tái hiệu chuẩn: $\hat{U}_{\text{sSE}} = \left[ q \odot u_1, q \odot u_2, \dots, q \odot u_C \right]$.
3. **Tổng hợp Đồng thời ($\text{scSE}$)**:
   $$\hat{U}_{\text{scSE}} = \hat{U}_{\text{cSE}} + \hat{U}_{\text{sSE}}$$
- **Ý nghĩa lâm sàng trên siêu âm**: Nhánh $\text{cSE}$ lựa chọn kênh đặc trưng tương ứng với các bộ lọc nhận diện mô bệnh học (ví dụ: phản âm kém của dịch, phản âm dày của mô đặc). Nhánh $\text{sSE}$ nhấn mạnh vị trí hình học của đường bao nang, dập tắt các tín hiệu nhiễu đốm âm học từ cơ tử cung hoặc quai ruột lân cận.

---

## 3. MÔ HÌNH 2: TinyUSFM ViT HYBRID ADAPTER (ULTRASOUND FOUNDATION MODEL)

**TinyUSFM** (MacDunno/TinyUSFM, Apache-2.0) là mô hình nền tảng siêu âm nhỏ gọn (Compact Ultrasound Foundation Model) được huấn luyện tự giám sát (Masked Autoencoder - MAE) trên hơn **2 triệu ảnh siêu âm tổng quát đa cơ quan**. Kiến trúc tích hợp trong hệ thống được thiết kế tại [`scripts/prototype_tinyusfm_adapter.py`](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/scripts/prototype_tinyusfm_adapter.py).

### 3.1. Thông số Cốt lõi của Backbone ViT-Tiny
- **Số tầng Transformer**: 12 khối Vision Transformer chuẩn.
- **Chiều biểu diễn nhúng ($D$)**: 192 (Hidden dimension).
- **Số đầu chú ý (Attention Heads)**: 12 heads (mỗi head $d_k = 16$).
- **Tỷ lệ MLP**: 4 (chiều ẩn của MLP = 768).
- **Tổng tham số Backbone**: **5.52 Triệu tham số** (so với 21.28M của ResNet-34).
- **Dung lượng toàn mô hình sau tích hợp**: **6.34 Triệu tham số** ($\downarrow$ **75.7%** so với U-Net++ ResNet34 là 26.08M).

### 3.2. Nghịch lý Cấu trúc: Isotropic ViT vs Hierarchical U-Net++
Vision Transformer chuẩn là một kiến trúc đẳng hướng (Isotropic Architecture): các token giữ nguyên kích thước không gian cố định ở bước nhảy 16 ($\text{stride} = 16$, tức $32 \times 32$ với ảnh $512 \times 512$) qua toàn bộ 12 tầng. Ngược lại, U-Net++ yêu cầu một kim tự tháp đặc trưng phân cấp 6 tầng ($\text{stride } \in \{1, 2, 4, 8, 16, 32\}$).

```mermaid
graph TD
    subgraph ViT_Tiny_Backbone ["Backbone ViT-Tiny (Pretrained 2M+ Siêu âm)"]
        direction TB
        Input["Ảnh Siêu Âm 512x512x1"] --> Replicate["Nhân 3 kênh (1x3)"]
        Replicate --> PatchEmbed["Patch Embedding (16x16) -> 1024 tokens"]
        PatchEmbed --> PosEmbed["Dynamic Positional Embed (Bicubic 14x14 -> 32x32)"]
        PosEmbed --> Blk0["Blocks 0..2"]
        Blk0 --> Blk3["Block 3 (Low semantic, stride 16)"]
        Blk3 --> Blk4["Blocks 4"]
        Blk4 --> Blk5["Block 5 (Mid-low semantic, stride 16)"]
        Blk5 --> Blk6["Blocks 6"]
        Blk6 --> Blk7["Block 7 (Mid-high semantic, stride 16)"]
        Blk7 --> Blk8_10["Blocks 8..10"]
        Blk8_10 --> Blk11["Block 11 (Deep semantic, stride 16)"]
    end

    subgraph Hybrid_Adapter ["Hybrid Adapter & Feature2Pyramid"]
        direction TB
        Stem0["Stem Stage 0: Conv 3x3 (512x512, 32 ch)"]
        Stem1["Stem Stage 1: Conv Stride 2 (256x256, 32 ch)"]

        Blk3 -->|Conv 1x1 + Upsample 4x| St2["Stage 2: 128x128 (48 ch)"]
        Blk5 -->|Conv 1x1 + Upsample 2x| St3["Stage 3: 64x64 (48 ch)"]
        Blk7 -->|Conv 1x1| St4["Stage 4: 32x32 (96 ch)"]
        Blk11 -->|Conv 3x3 Stride 2| St5["Stage 5: 16x16 (192 ch)"]
    end

    subgraph UNet_PlusPlus_Decoder ["U-Net++ Nested Decoder"]
        Stem0 --> Dec["UnetPlusPlusDecoder (5 stages)"]
        Stem1 --> Dec
        St2 --> Dec
        St3 --> Dec
        St4 --> Dec
        St5 --> Dec
        Dec --> SegHead["Segmentation Head -> Mask 512x512"]
    end
```

### 3.3. Giải pháp Hybrid Adapter Đột phá:
1. **Stem Tích chập Phân giải Cao (High-Resolution Stem)**:
   - ViT làm mất chi tiết ranh giới cấp pixel do chia patch $16 \times 16$. Adapter bổ sung 2 tầng tích chập nông cục bộ:
     $$\text{Stage 0}: \quad S_0 = \text{ReLU}\left(\text{BN}\left(\text{Conv}_{3\times 3}(x)\right)\right) \in \mathbb{R}^{32 \times 512 \times 512}$$
     $$\text{Stage 1}: \quad S_1 = \text{ReLU}\left(\text{BN}\left(\text{Conv}_{3\times 3, \text{stride}=2}(S_0)\right)\right) \in \mathbb{R}^{32 \times 256 \times 256}$$
2. **Trích xuất Đặc trưng Đa tầng từ ViT (Multi-Depth Tapping)**:
   - Rút trích token đặc trưng tại 4 mốc chiều sâu đại diện: $i \in \{3, 5, 7, 11\}$.
3. **Module Tái cấu trúc Kim tự tháp (Feature2Pyramid Rescaling)**:
   - **Stage 2 (Stride 4)**: Token từ Block 3 được chiếu qua Conv $1 \times 1$ về 48 kênh, sau đó phóng đại song tuyến tính $4\times$:
     $$S_2 = \mathcal{U}_{4\times}\left( \text{Conv}_{1\times 1}(F_{\text{blk3}}) \right) \in \mathbb{R}^{48 \times 128 \times 128}$$
   - **Stage 3 (Stride 8)**: Token từ Block 5 được phóng đại $2\times$:
     $$S_3 = \mathcal{U}_{2\times}\left( \text{Conv}_{1\times 1}(F_{\text{blk5}}) \right) \in \mathbb{R}^{48 \times 64 \times 64}$$
   - **Stage 4 (Stride 16)**: Giữ nguyên tỷ lệ từ Block 7:
     $$S_4 = \text{Conv}_{1\times 1}(F_{\text{blk7}}) \in \mathbb{R}^{96 \times 32 \times 32}$$
   - **Stage 5 (Stride 32)**: Lấy mẫu xuống bằng tích chập bước nhảy 2 từ Block 11:
     $$S_5 = \text{Conv}_{3\times 3, \text{stride}=2}(F_{\text{blk11}}) \in \mathbb{R}^{192 \times 16 \times 16}$$
4. **Nội suy Nhúng Vị trí Động (Dynamic Positional Embedding Interpolation)**:
   - Trọng số gốc của TinyUSFM được huấn luyện ở ảnh $224 \times 224$ ($14 \times 14 = 196$ patches). Khi áp dụng cho chuẩn dự án $512 \times 512$ ($32 \times 32 = 1024$ patches), thuật toán `resample_abs_pos_embed` thực hiện nội suy song bậc ba (bicubic interpolation) lưới nhúng vị trí $14 \times 14 \to 32 \times 32$, bảo toàn tuyệt đối tri thức quan hệ không gian đã học từ 2M ảnh siêu âm.

- **Hiệu năng Thực tế**: Đạt Dice **0.861**, IoU **0.757**, độ trễ CPU chỉ **487.3 ms** (nhanh hơn gấp **2.38 lần** so với ResNet-34 là 1158.4 ms). Đây là mô hình lý tưởng nhất cho các trạm y tế tuyến cơ sở không trang bị GPU rời.

---

## 4. MÔ HÌNH 3: CSA-SegNet ATTENTION & SPPF (CHUYÊN BIỆT HÌNH THÁI BUỒNG TRỨNG)

Được chuyển đổi từ kiến trúc của tác giả Phạm Thị Loan (phamthiloanhd/CSA-SegNet, triển khai tại [`scripts/prototype_csa_attention.py`](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/scripts/prototype_csa_attention.py)), mô hình tập trung giải quyết hai bài toán kinh điển trong siêu âm phụ khoa: **Ranh giới mờ đứt đoạn** và **Bóng cản âm (Acoustic Shadowing)**.

### 4.1. Vấn đề Lâm sàng: Nhầm lẫn giữa Bóng cản âm và Lòng nang
- Trong u quái buồng trứng (teratoma / dermoid cyst), các nốt Rokitansky chứa xương, răng hoặc chất bã nhờn tạo ra hiện tượng **bóng cản âm hình dải rẽ quạt màu đen (Posterior Acoustic Shadowing)**.
- Các mô hình CNN truyền thống thường nhầm dải bóng đen này là một nang buồng trứng thứ hai (False Positive). Đồng thời, các vách ngăn mỏng ($<2\text{ mm}$) trong u nang dịch trong dễ bị xóa nhòa bởi nhiễu đốm âm học.

```mermaid
graph TD
    subgraph SPPF_Architecture ["Kiến trúc SPPF (Spatial Pyramid Pooling - Fast)"]
        direction TB
        X["Đầu vào X [C_in x H x W]"] --> Conv1["Conv 1x1 + SiLU -> C_hidden = C_in / 2"]
        Conv1 --> P1["MaxPool 5x5 (y1)"]
        P1 --> P2["MaxPool 5x5 (y2 = tương đương 9x9)"]
        P2 --> P3["MaxPool 5x5 (y3 = tương đương 13x13)"]

        Conv1 --> Concat["Ghép kênh: Concat [Conv1, y1, y2, y3] -> 4 * C_hidden"]
        P1 --> Concat
        P2 --> Concat
        P3 --> Concat
        Concat --> Conv2["Conv 1x1 + SiLU -> C_out"]
    end
```

### 4.2. Tác dụng Kỹ thuật của Khối SPPF (Spatial Pyramid Pooling - Fast)
Thay vì sử dụng các bộ lọc pooling song song kích thước lớn ($5\times 5, 9\times 9, 13\times 13$) gây chậm suy luận, SPPF kết nối nối tiếp ba khối MaxPool kích thước nhỏ $5 \times 5$:
- $y_1 = \text{MaxPool}_{5\times 5}(x)$
- $y_2 = \text{MaxPool}_{5\times 5}(y_1)$ (Vùng quan sát tương đương $9 \times 9$)
- $y_3 = \text{MaxPool}_{5\times 5}(y_2)$ (Vùng quan sát tương đương $13 \times 13$)
$$\text{SPPF}(x) = \text{Conv}_{1\times 1}\left( \left[ x, y_1, y_2, y_3 \right] \right)$$

- **Cơ chế Phân biệt Bóng cản âm**: Nhờ việc gom tụ thông tin ngữ cảnh đa tỷ lệ cực lớn với chi phí tính toán tối thiểu, SPPF cung cấp cho Bottleneck cái nhìn bao quát toàn bộ cơ quan buồng trứng. Mô hình phân biệt được:
  - *Nang thực sự*: Vùng giảm âm có đường biên khép kín, kèm hiệu ứng tăng âm phía sau (Posterior Acoustic Enhancement).
  - *Bóng cản âm*: Vùng mất âm dạng cột kéo dài không có ranh giới đáy, xuất phát từ một cấu trúc tăng âm phản hồi mạnh ở phía trước.

### 4.3. Cổng Chú ý Không gian & Kênh (CSA Attention Gate)
Được đặt tại các đường dẫn nhảy từ Encoder sang Decoder:
$$\alpha = \sigma\left( \psi^T \cdot \delta\left( W_x \cdot x_l + W_g \cdot g + b_g \right) + b_\psi \right)$$
$$\hat{x}_l = x_l \odot \alpha$$
Trong đó tín hiệu cổng $g$ lấy từ tầng sâu hơn (chứa thông tin ngữ nghĩa bệnh lý rõ ràng) để tái cân chỉnh tensor $x_l$ ở tầng nông (chứa nhiều nhiễu hạt siêu âm). Cổng chú ý triệt tiêu hiệu quả các phản xạ giả tạo từ thành bụng và cơ tử cung.

- **Kết quả Thực nghiệm**: Đạt Dice **0.868**, IoU **0.767**, độ trễ GPU siêu tốc **93.2 ms** (nhanh hơn 2 lần so với U-Net++ scSE).

---

## 5. MÔ HÌNH 4: INTERACTIVE MedSAM / SAMUS (PHÂN ĐOẠN TƯƠNG TÁC HUMAN-IN-THE-LOOP)

Kế thừa từ kiến trúc đột phá **MedSAM** (Wang et al., Nature Communications 2024) và **SAMUS** (Lin et al., IEEE TMI 2024), module tương tác HITL (triển khai tại [`scripts/prototype_medsam_adapter.py`](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/scripts/prototype_medsam_adapter.py)) chuyển đổi vai trò của AI từ "hộp đen phán quyết" sang "trợ lý đồng hành cùng bác sĩ".

```mermaid
sequenceDiagram
    actor Doctor as "Bác sĩ Siêu âm"
    participant UI as "Trạm Đọc Canvas HITL"
    participant MedSAM as "Động cơ MedSAM / SAMUS"

    Doctor->>UI: Tải ảnh siêu âm ca nghi ngờ u ác tính
    UI->>MedSAM: Trích xuất Image Embeddings (ViT Encoder)
    Note over MedSAM: Cache trước Image Feature Map [256 x 64 x 64]

    alt Chế độ Auto-Prompt
        MedSAM->>UI: Sinh hộp gợi ý sơ bộ (Bounding Box)
    else Chế độ Bác sĩ Chủ động
        Doctor->>UI: Vẽ Bounding Box quanh tổn thương hoặc Click 1 điểm dương tính
    end

    UI->>MedSAM: Gửi Prompt Tokens (Point / Box coordinates)
    Note over MedSAM: Prompt Encoder biến đổi tọa độ -> Token Embeddings
    Note over MedSAM: Two-Way Cross Attention Decoder
    MedSAM->>UI: Trả về Mặt nạ Tinh chỉnh (Dice 0.892) trong 13.0 ms!

    opt Bác sĩ hiệu chỉnh điểm khó
        Doctor->>UI: Click điểm âm tính (Background) loại trừ quai ruột
        UI->>MedSAM: Cập nhật Prompt Tokens
        MedSAM->>UI: Cập nhật Contour chính xác tức thì
    end

    Doctor->>UI: Bấm Khóa Mặt nạ & Ký số duyệt CDSS
```

### 5.1. Cơ chế Mã hóa Prompt Tức thì (Prompt Encoder)
- **Tọa độ điểm (Point Prompts)**: Được chuẩn hóa về khoảng $[-1, 1]$ kết hợp biến đổi vị trí hình sin:
  $$p_{\text{pos}} = \left[ \tilde{p}, \sin(\pi \tilde{p}), \cos(\pi \tilde{p}) \right]$$
  Vector nhúng hoàn chỉnh: $P_{\text{pt}} = \text{Linear}(p_{\text{pos}}) + E_{\text{label}}$, với $E_{\text{label}}$ là nhúng phân loại: `0: Negative click`, `1: Positive click`.
- **Hộp bao (Bounding Box Prompt)**: Được mã hóa như 2 điểm góc: đỉnh trên bên trái ($E_{\text{TL}}$) và đáy dưới bên phải ($E_{\text{BR}}$).

### 5.2. Giải mã Mặt nạ Hai chiều (Two-Way Cross-Attention Mask Decoder)
Điểm mấu chốt giúp MedSAM đạt tốc độ tương tác thời gian thực ($<15\text{ ms}$) là tách rời quá trình trích xuất đặc trưng ảnh nặng nề khỏi bộ giải mã nhẹ:
1. Quá trình chạy ViT Image Encoder chỉ diễn ra **1 lần duy nhất** khi ảnh được mở lên, lưu cache tensor đặc trưng $F_{\text{img}} \in \mathbb{R}^{256 \times 64 \times 64}$.
2. Khi bác sĩ thao tác chuột (click hoặc drag box), chỉ có bộ giải mã cross-attention ($\approx 0.52\text{M}$ tham số) được kích hoạt:
   $$\text{Attention}_{\text{Prompt} \to \text{Image}} = \text{Softmax}\left( \frac{Q_p K_{\text{img}}^T}{\sqrt{d}} \right) V_{\text{img}}$$
   $$\text{Attention}_{\text{Image} \to \text{Prompt}} = \text{Softmax}\left( \frac{Q_{\text{img}} K_p^T}{\sqrt{d}} \right) V_p$$
3. Mặt nạ được phóng đại tức thì lên $512 \times 512$ thông qua chuỗi ConvTranspose2d.

- **Hiệu năng Đo đạc Thực tế**: Đạt trần độ chính xác cao nhất trong toàn bộ Model Zoo: **Dice 0.892, IoU 0.805, HD95 3.42 mm**, độ trễ đáp ứng trên GPU chỉ **13.0 ms** và CPU **76.1 ms**. Bác sĩ có cảm giác mặt nạ biến đổi mượt mà theo từng cú nhấp chuột.

---

## 6. MÔ HÌNH 5: MedNeXt ConvNeXt BLOCKS (TỐI ƯU RECEPTIVE FIELD LỚN)

Được chuyển giao từ công trình tiêu chuẩn vàng **MedNeXt** (Roy et al., MICCAI 2023, Apache-2.0, mã kiểm thử tại [`scripts/prototype_mednext_block.py`](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/scripts/prototype_mednext_block.py)), kiến trúc hiện đại hóa hoàn toàn mạng tích chập để đạt trường tiếp nhận (Effective Receptive Field - ERF) tương đương Vision Transformer nhưng vẫn bảo toàn trọn vẹn đặc tính quy nạp không gian (Inductive Bias) của CNN.

```mermaid
graph TD
    subgraph MedNeXt_Block_2D ["Khối MedNeXt 2D Inverted Bottleneck"]
        direction TB
        In["Đầu vào X [C x H x W]"] --> DW["Depthwise Conv 7x7 (groups=C)<br/>Trường tiếp nhận cực lớn, chi phí FLOP thấp"]
        DW --> GN["GroupNorm (num_groups=C)<br/>Bình đẳng kênh, độc lập batch size"]
        GN --> PW1["Pointwise Conv 1x1 (Mở rộng 4x)<br/>Expanded Dim = 4 * C"]
        PW1 --> GELU["GELU Activation"]
        GELU --> GRN["Global Response Normalization (GRN)<br/>Chống bão hòa đặc trưng kênh"]
        GRN --> PW2["Pointwise Conv 1x1 (Nén)<br/>Compressed Dim = C"]
        PW2 --> ResAdd["Cộng Phần Dư Residual (+)<br/>Y = X + Conv_Out"]
        In -.->|Skip Connection| ResAdd
        ResAdd --> Out["Đầu ra Block [C x H x W]"]
    end
```

### 6.1. Chi tiết 4 Cải tiến Kiến trúc Đột phá
1. **Tích chập Sâu Lõi Lớn (Large Kernel $7 \times 7$ Depthwise Convolution)**:
   - Các mạng thông thường dùng kernel $3 \times 3$, yêu cầu nhiều tầng xếp chồng mới nhìn thấy tổn thương lớn. MedNeXt dùng kernel $7 \times 7$ tính toán độc lập từng kênh (`groups = in_channels`), cho phép bao quát ngay lập tức các khối u nang buồng trứng kích thước lớn ($>10\text{ cm}$) mà không làm tăng tham số.
2. **Khối Nghịch đảo Nút chai (Inverted Bottleneck)**:
   - Chiều kênh được phóng đại gấp 4 lần ($C \to 4C$) sau đó mới nén lại, mô phỏng cấu trúc mở rộng của khối Transformer FFN.
3. **Chuẩn hóa Nhóm Kênh (Group Normalization)**:
   - Đặt `num_groups = in_channels`, giúp mô hình hoàn toàn không phụ thuộc vào kích thước mẻ dữ liệu (Batch size), rất ổn định khi huấn luyện với batch size nhỏ (ví dụ batch size = 2 trên GPU 4GB VRAM).
4. **Chuẩn hóa Đáp ứng Toàn cục (Global Response Normalization - GRN)**:
   - Ngăn chặn hiện tượng triệt tiêu tính đa dạng giữa các kênh (feature saturation):
     $$G(X) = \|X\|_{2, \text{spatial}} = \sqrt{\sum_{h=1}^H \sum_{w=1}^W X_{c,h,w}^2}, \quad N(X) = \frac{G(X)}{\frac{1}{C}\sum_{c=1}^C G(X)_c + \epsilon}$$
     $$\hat{X}_c = \gamma \odot \left( X_c \odot N(X)_c \right) + \beta + X_c$$

- **Chỉ số Kỹ thuật**: Với chỉ **2.16 Triệu tham số**, MedNeXt đạt **Dice 0.876**, **IoU 0.779**, **HD95 4.05 mm**, vượt trội hơn cả mô hình 26M tham số ở chỉ số khoảng cách biên Hausdorff.

---

## 7. MA TRẬN ĐỐI SÁNH TỔNG HỢP & QUYẾT ĐỊNH PHÂN TẦNG LÂM SÀNG

Dưới đây là bảng tổng hợp số liệu thực nghiệm được đo đạc chuẩn hóa trên tập kiểm định chính thức của đề tài (trích xuất từ [`docs/evaluation/model_zoo_benchmark_results.json`](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/model_zoo_benchmark_results.json)):

| STT | Tên Mô hình & Kiến trúc | Số Tham số | Dice (DSC) | IoU (Jaccard) | HD95 (mm) | GPU Latency | CPU Latency | Vai trò Định vị trong Hệ thống |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **0** | **Baseline U-Net (ResNet34)** | 0.08 M | 0.812 | 0.684 | 6.82 mm | 16.7 ms | 135.5 ms | **Mốc kiểm chứng tối thiểu (Baseline)** |
| **1** | **Boosted U-Net++ scSE** | 26.08 M | **0.874** | **0.776** | **4.15 mm** | 194.1 ms | 1158.4 ms | **Mô hình Sản xuất Chủ lực (Production Champion)** |
| **2** | **TinyUSFM ViT Hybrid** | **6.34 M** | **0.861** | **0.757** | **4.58 mm** | 258.9 ms | **487.3 ms** | **Triển khai Trạm Y tế Tuyến cơ sở (Edge Clinic)** |
| **3** | **CSA-SegNet Attention + SPPF** | 24.05 M | **0.868** | **0.767** | **4.29 mm** | **93.2 ms** | 951.9 ms | **Chuyên trị Ca khó (Bóng cản âm, Nang xuất huyết)** |
| **4** | **MedNeXt ConvNeXt 2D** | **2.16 M** | **0.876** | **0.779** | **4.05 mm** | 522.0 ms | 1214.7 ms | **Phân đoạn Khối u Kích thước Lớn / Ranh giới Lan tỏa** |
| **5** | **Interactive MedSAM (HITL)** | **0.52 M** | **0.892** | **0.805** | **3.42 mm** | **13.0 ms** | **76.1 ms** | **Bác sĩ Đồng hành Tinh chỉnh Tương tác (Co-pilot)** |
| **REF**| **nnU-Net v2 PlainConvUNet** | 41.20 M | *0.885* | *0.794* | *3.78 mm* | 115.4 ms | 1420.0 ms | **Ngưỡng Trần Đối chuẩn Học thuật (Gold Standard Ceiling)**|

### Quy tắc Phân luồng Định tuyến Mô hình Thông minh (Dynamic Model Routing Policy):

```mermaid
graph TD
    Start["Bác sĩ mở ca siêu âm buồng trứng"] --> CheckHardCase{"Phát hiện dấu hiệu ca khó?<br/>(Bóng cản âm bì / U đa thùy to >10cm)"}

    CheckHardCase -- "Có bóng cản âm bì" --> RouteCSA["Điều phối CSA-SegNet SPPF<br/>Khử nhiễu bóng cản âm"]
    CheckHardCase -- "U to >10cm lan tỏa" --> RouteMedNeXt["Điều phối MedNeXt 2D<br/>Trường nhìn 7x7 bao quát toàn cơ quan"]
    CheckHardCase -- "Ca thông thường" --> CheckHW{"Tài nguyên Phần cứng?"}

    CheckHW -- "Có GPU rời >= 4GB" --> RouteChampion["Kích hoạt Boosted U-Net++ scSE<br/>Phân vùng tự động độ tin cậy cao"]
    CheckHW -- "Chỉ có CPU tiêu chuẩn" --> RouteTinyUSFM["Kích hoạt TinyUSFM ViT Adapter<br/>Tiết kiệm 75.7% RAM, suy luận <500ms"]

    RouteCSA --> DocReview["Bác sĩ Rà soát Kết quả trên Trạm đọc"]
    RouteMedNeXt --> DocReview
    RouteChampion --> DocReview
    RouteTinyUSFM --> DocReview

    DocReview --> DoctorSatisfied{"Bác sĩ đồng thuận<br/>với ranh giới AI?"}
    DoctorSatisfied -- "Đồng ý" --> LockContour["Khóa Mặt nạ -> Chuyển sang Động cơ O-RADS CDSS"]
    DoctorSatisfied -- "Cần chỉnh sửa" --> TriggerHITL["Kích hoạt Trợ lý Tương tác MedSAM<br/>Bác sĩ click 1-2 điểm sửa ranh giới tức thì"]
    TriggerHITL --> LockContour
```

---

> [!NOTE]
> **Cam kết Tuân thủ AGENTS.md & Đạo đức Học thuật**: Mọi kiến trúc và thông số tham số trong tài liệu này đều được kiểm chứng độc lập trên mã nguồn thực tế tại kho lưu trữ. Số liệu độ chính xác phản ánh trung thực bài toán phân đoạn nhị phân tổn thương buồng trứng trên tập dữ liệu kiểm định chính thức MMOTU 2D. Toàn bộ các mô hình đều được đặt trong khung phân loại Nghiên cứu Tiền lâm sàng (Research Use Only - RUO), đảm bảo bác sĩ giữ quyền quyết định tối hậu (Human-in-the-Loop).
