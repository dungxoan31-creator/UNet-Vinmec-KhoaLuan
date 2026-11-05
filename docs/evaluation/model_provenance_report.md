# BÁO CÁO TRUY NGUYÊN NGUỒN GỐC MÔ HÌNH VÀ CHECKPOINTS (MODEL PROVENANCE REPORT)
**Thời điểm lập báo cáo**: 2026-10-30T00:15:00+07:00
**Trạng thái**: Đã truy nguyên trung thực; KHÔNG đổi nhãn checkpoint.

## 1. Bảng Kiểm kê Checkpoint & SHA-256 Manifest

| Tên file checkpoint | Đường dẫn tương đối | Kích thước (MB) | SHA-256 Digest |
|---|---|---|---|
| baseline_unet_best.pth | checkpoints/archive_milestone_1/baseline_unet_best.pth | 29.67 MB | 44b862d400f229992e67994e5945cbdb4d22ce924b8aa923f01e75fac5215696 |
| baseline_unet_best.pth | checkpoints/baseline_unet_best.pth | 29.67 MB | 5e14be07240966f74de91d3467edbf88a08ca07b6577081787c6abd6dede494e |
| boosted_unetplusplus_mmotu_stage1_best.pth | checkpoints/boosted_unetplusplus_multi_source_2026-10-27/stage1_mmotu/boosted_unetplusplus_mmotu_stage1_best.pth | 99.67 MB | 095f80479e31798bc62721eb17c21f99c70079d694277f0fd987c92cfa75333f |
| boosted_unetplusplus_mmotu_stage1_last.pth | checkpoints/boosted_unetplusplus_multi_source_2026-10-27/stage1_mmotu/boosted_unetplusplus_mmotu_stage1_last.pth | 99.67 MB | b4dacbc99cdb67dfa4ed94c9e3e22cb0330f25a08369d152a19a34f73e14c739 |
| boosted_resnet34_scse_best.pth | checkpoints/boosted_unetplusplus_scse_2026-10-27/boosted_resnet34_scse_best.pth | 100.5 MB | 67624bbb0e50e236df7b5c82736eaadab1ff1fff5547c5e813bca545c2dd2045 |
| boosted_resnet34_scse_last.pth | checkpoints/boosted_unetplusplus_scse_2026-10-27/boosted_resnet34_scse_last.pth | 100.5 MB | bb4efbfcac074bbad7907565efd8c8fa1b1ae550ead836e562a997518b50efaf |
| finetune_2d_final.pth | checkpoints/finetune_2d/finetune_2d_final.pth | 29.67 MB | 5d02327dbe65a84e435a41321f1349a0e4301a956a15b3cced1177799d2859f6 |
| vinmec_unet_best.pth | checkpoints/full_dataset_2026-10-03/Vinmec_2D/vinmec_unet_best.pth | 29.67 MB | 2345f36b6787d960f2a633ee0f108bbdeb0032d414a780f233e746bab920f00c |
| vinmec_unet_best.pth | checkpoints/full_dataset_2026-10-03/Vinmec_CEUS/vinmec_unet_best.pth | 29.67 MB | 3963dec6fe8e0c2d980f450251a60e377e5399ee74020f33bbc9b0530d099e22 |
| vinmec_unet_best.pth | checkpoints/full_dataset_2026-10-03/Vinmec_Split_2D/vinmec_unet_best.pth | 29.67 MB | 7b99d794486bef9433cee0d1a0b9c790618257f09cd04fb32a4f2eb57a286763 |
| vinmec_unet_best.pth | checkpoints/full_dataset_2026-10-03/Vinmec_Split_CEUS/vinmec_unet_best.pth | 29.67 MB | 3963dec6fe8e0c2d980f450251a60e377e5399ee74020f33bbc9b0530d099e22 |
| full_unet_final.pth | checkpoints/full_unet_final.pth | 29.67 MB | 06238d8d87d35e70d510314a3019a8ee2b325dc56662bf0fb57c4726ca6a9bdb |
| mmotu_resnet34_8class_best.pth | checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_01_balanced_256_finetune_lr1e4/mmotu_resnet34_8class_best.pth | 81.35 MB | b90cda6d8b4b5ceb270eee6e145492bdd28b3a8b94e01d8646d9ca1f0d063aaf |
| mmotu_resnet34_8class_last.pth | checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_01_balanced_256_finetune_lr1e4/mmotu_resnet34_8class_last.pth | 81.35 MB | 5a9c5ea2a4f554fa3382adb89cc79270c0b3c69f36c5c4a01bd479b039da64cc |
| mmotu_resnet34_8class_best.pth | checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_02_balanced_256_finetune_lr5e5/mmotu_resnet34_8class_best.pth | 81.35 MB | 35737b75c89b983a5b51846aba45aebea3144b8d09f70f1e3cfc1f08b1118a92 |
| mmotu_resnet34_8class_last.pth | checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_02_balanced_256_finetune_lr5e5/mmotu_resnet34_8class_last.pth | 81.35 MB | d06ba7a2b65aa990ca38ec66bb52dcb25dfc24ffc6e22c58cc7fccaeea991170 |
| mmotu_resnet34_8class_best.pth | checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_03_balanced_384_linear_probe/mmotu_resnet34_8class_best.pth | 81.35 MB | c7e5267838a287203385ddd4d9ad6b6475ece987c25844fdb438be8fc75a5d49 |
| mmotu_resnet34_8class_last.pth | checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_03_balanced_384_linear_probe/mmotu_resnet34_8class_last.pth | 81.35 MB | 3b45bd29b6621218c11d7a07c07c239bb4c0f48dd4b40abc8ec23e9d68a25b85 |
| mmotu_resnet34_8class_best.pth | checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_04_weighted_256_finetune/mmotu_resnet34_8class_best.pth | 81.35 MB | 96d900fd57c44f5874363c159fce13cf61864827fbeaef66f34da1eeab189cf1 |
| mmotu_resnet34_8class_last.pth | checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_04_weighted_256_finetune/mmotu_resnet34_8class_last.pth | 81.35 MB | 0418a07a9749d9eae9b258a38de7595bd539226a0c7852cfae8101b2ba3de104 |
| mmotu_resnet34_8class_best.pth | checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_05_balanced_384_finetune_lr3e5/mmotu_resnet34_8class_best.pth | 81.35 MB | b410ad3e24fb5738985999d9316184965a662c641f2bf95adf0f9bd5237354c5 |
| mmotu_resnet34_8class_last.pth | checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_05_balanced_384_finetune_lr3e5/mmotu_resnet34_8class_last.pth | 81.35 MB | 549c8bdd15caf4b7afced359a7859b591dd88c9eee540233e3939a09c14156dd |
| mmotu_resnet34_8class_best.pth | checkpoints/mmotu_8class_classifier_2026-10-27/mmotu_resnet34_8class_best.pth | 81.35 MB | 9b508d4dc2dcc704408bdc0d69d2c3abd24c2f23f3edfc4eb6c730c4c4294c44 |
| mmotu_resnet34_8class_last.pth | checkpoints/mmotu_8class_classifier_2026-10-27/mmotu_resnet34_8class_last.pth | 81.35 MB | 618bed7c717a5d7a671b794bb455eaa3ebf637e7cf41cda9806f03cf73a15c9b |
| mmotu_resnet34_8class_best.pth | checkpoints/mmotu_8class_classifier_2026-10-27_balanced/mmotu_resnet34_8class_best.pth | 81.35 MB | 6a5d3589b9e7ebd8ea357a1ccb713932e1cc50bc7908af278b8108667825129e |
| mmotu_resnet34_8class_last.pth | checkpoints/mmotu_8class_classifier_2026-10-27_balanced/mmotu_resnet34_8class_last.pth | 81.35 MB | e20995fa9e27d1c79caee856c65a0999d3d14423f23a653125cbf68f7f440159 |
| vinmec_unet_best.pth | checkpoints/retrain_2d_2026-10-03/vinmec_unet_best.pth | 29.67 MB | 291ed5deb4c1563cd6d35d90482591d15c10ed74461939bfefcf328d6656dfaa |
| vinmec_unet_best.pth | checkpoints/retrain_2d_2026-10-03_stable/vinmec_unet_best.pth | 29.67 MB | 5e14be07240966f74de91d3467edbf88a08ca07b6577081787c6abd6dede494e |
| standard_unet_best.pth | checkpoints/standard_unet_gray_imagenet_norm_2026-10-06/standard_unet_best.pth | 29.67 MB | 1269a7d3a251df25ae25a4d6c146f667201c8063c90a9c26e59e3a9eefa71879 |
| standard_unet_last.pth | checkpoints/standard_unet_gray_imagenet_norm_2026-10-06/standard_unet_last.pth | 29.67 MB | e32456c2bc5d622c1598bbd2e83eabb0deda4205c76226b3966f117caa3ae665 |
| unetplusplus_resnet34_best.pth | checkpoints/unetplusplus_resnet34_2026-10-06/unetplusplus_resnet34_best.pth | 99.66 MB | ce7580329fd8cab47cf7418e5a5ebd212bf70847983c57f352dc77a98e591e76 |
| unetplusplus_resnet34_last.pth | checkpoints/unetplusplus_resnet34_2026-10-06/unetplusplus_resnet34_last.pth | 99.66 MB | 0a84eddcc5eb13a6693f9920e3215cbd3077369cae65dc499e6d19c1b0b4d227 |
| unetplusplus_resnet34_best.pth | checkpoints/unetplusplus_resnet34_retrained/unetplusplus_resnet34_best.pth | 99.66 MB | ce7580329fd8cab47cf7418e5a5ebd212bf70847983c57f352dc77a98e591e76 |
| unetplusplus_resnet34_last.pth | checkpoints/unetplusplus_resnet34_retrained/unetplusplus_resnet34_last.pth | 99.66 MB | 0a84eddcc5eb13a6693f9920e3215cbd3077369cae65dc499e6d19c1b0b4d227 |
| baseline_unet_best.pth | checkpoints/unified_vinmec_2026-10-06/baseline_unet_best.pth | 29.67 MB | 509b050f633f765b03419d1615397557889c9c647dd24d500446fa3495d8198b |
| baseline_unet_last.pth | checkpoints/unified_vinmec_2026-10-06/baseline_unet_last.pth | 29.67 MB | 0724ff53368d7e6544c8694821b0771562dfbea0fc9dfffe531c6d5fcc880906 |
| baseline_unet_best.pth | checkpoints/unified_vinmec_refine_2026-10-06/lr_1e-04/baseline_unet_best.pth | 29.67 MB | 902d8f7bdbede4fa0cfa756929c1c0c44791a35bdb94214c8415eaec26d69801 |
| baseline_unet_last.pth | checkpoints/unified_vinmec_refine_2026-10-06/lr_1e-04/baseline_unet_last.pth | 29.67 MB | 1f79b713596b55828cc09c67f8f6b2ab9c6bbaaec8e5fd4c5460d58f841ade0e |
| baseline_unet_best.pth | checkpoints/unified_vinmec_refine_2026-10-06/lr_3e-04/baseline_unet_best.pth | 29.67 MB | 417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d |
| baseline_unet_last.pth | checkpoints/unified_vinmec_refine_2026-10-06/lr_3e-04/baseline_unet_last.pth | 29.67 MB | 47d7ba8ccdd6543178b1feb5d251f71603aa5c3361dea6a1a393cc8576dc2196 |
| vinmec_unet_best.pth | checkpoints/vinmec_unet_best.pth | 29.67 MB | 5c8d40f64b49f76dd0cb0ece250a9fb39ccfc1bbdd6bbba10ad1d9f9f1f540f0 |

## 2. Đối chiếu Hàm Mất mát (Loss Function Reconciliation)
- **Cấu hình lý thuyết theo Đề cương**: Combo Loss ({\text{Dice}} + L_{\text{BCE}}$) với hệ số cân bằng $.
- **Thực tế trong Checkpoint Lịch sử**: Các checkpoint ban đầu (aseline_unet_best.pth, inmec_unet_best.pth) được huấn luyện với AdvancedHybridLoss (kết hợp Dice Loss + Focal Loss + Tversky/Boundary Loss) tại ngưỡng threshold 0.40.
- **Kết luận truy nguyên**: Giữ nguyên toàn bộ checkpoint hiện hữu, không đổi tên hoặc dán lại nhãn (relabel) nhằm che giấu sự khác biệt. Sự khác biệt giữa AdvancedHybridLoss và ComboLoss được ghi nhận minh bạch trong hồ sơ giả định A6.

## 3. Khả năng Tái lập và Huấn luyện lại (Reproducibility & Retraining)
- Toàn bộ mã nguồn huấn luyện mô hình được lưu trữ tại i_training/ (	rain_boosted_unetplusplus.py, 	rain_multi_source_boosted.py, loss.py).
- Việc huấn luyện lại quy mô lớn đòi hỏi GPU chuyên dụng và thời gian dài; việc giữ nguyên mô hình và báo cáo đúng thực tế đảm bảo tính trung thực khoa học cao nhất của khóa luận.