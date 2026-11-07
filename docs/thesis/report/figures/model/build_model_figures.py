"""Reproduce thesis figures from the frozen experiment files, without running inference."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cv2
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from backend.core.dataset_paths import resolve_dataset_path
from backend.services.preprocessor import UltrasoundPreprocessor
OUT = Path(__file__).resolve().parent
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                     'axes.spines.right': False, 'svg.fonttype': 'none'})
COLORS = ['#23526e', '#178077']
configs = [ROOT / 'checkpoints/standard_unet_gray_imagenet_norm_2026-10-06',
           ROOT / 'checkpoints/unetplusplus_resnet34_2026-10-06']
labels = ['Standard U-Net đồng chuẩn hóa', 'U-Net++ / ResNet34 pretrained']
histories = [json.loads((p/'training_history.json').read_text()) for p in configs]
manifest = []

def save(fig, name, sources):
    fig.tight_layout()
    for extension in ['png', 'svg']:
        fig.savefig(OUT/f'{name}.{extension}', dpi=250, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    manifest.append({'figure': name, 'sources': sources})

fig, axes = plt.subplots(2, 1, figsize=(6.3, 6.3))
for idx, records in enumerate(histories):
    epochs = [x['epoch'] for x in records]
    for ax, mode in zip(axes, ['train', 'validation']):
        ax.plot(epochs, [x[mode]['loss'] for x in records], color=COLORS[idx], label=labels[idx], lw=1.8)
        ax.set(xlabel='Epoch', ylabel='Combo Loss', title='Train' if mode=='train' else 'Validation')
        ax.grid(alpha=.18)
axes[1].legend(fontsize=9)
save(fig, 'duong-loss', [str(p.relative_to(ROOT)/'training_history.json') for p in configs])

fig, axes = plt.subplots(2, 1, figsize=(6.3, 6.3))
for idx, records in enumerate(histories):
    epochs = [x['epoch'] for x in records]
    for ax, mode in zip(axes, ['train', 'validation']):
        ax.plot(epochs, [x[mode]['dice'] for x in records], color=COLORS[idx], label=labels[idx], lw=1.8)
        ax.set(xlabel='Epoch', ylabel='Dice trung bình theo ảnh', ylim=(0,1), title='Train' if mode=='train' else 'Validation')
        ax.grid(alpha=.18)
axes[1].legend(fontsize=9)
save(fig, 'duong-dice', [str(p.relative_to(ROOT)/'training_history.json') for p in configs])

comparison = ROOT/'evaluation/milestone_3_2026-10-06/model_comparison_validation.json'
models = json.loads(comparison.read_text())['models'][1:]
names = ['Dice', 'IoU', 'Recall', 'Precision']
fig, ax = plt.subplots(figsize=(6.3,4.5))
x = np.arange(4)
for idx, model in enumerate(models):
    values = [model['validation_metrics'][m.lower()] for m in names]
    bars = ax.bar(x+(idx-.5)*.34, values, width=.34, color=COLORS[idx], label=labels[idx])
    ax.bar_label(bars, fmt='%.3f', fontsize=9, padding=3)
ax.set(xticks=x, xticklabels=names, ylim=(0,1), ylabel='Macro theo 541 ảnh Validation')
ax.legend(loc='lower right', fontsize=9)
ax.grid(axis='y',alpha=.15)
save(fig, 'so-sanh-validation', [str(comparison.relative_to(ROOT))])

csv = ROOT/'evaluation/milestone_3_2026-10-06/test_per_image.csv'
data = pd.read_csv(csv)
fig, axes = plt.subplots(2, 1, figsize=(6.3,6.3))
axes[0].hist(data.dice, bins=np.linspace(0,1,21),color=COLORS[0],edgecolor='white')
axes[0].axvline(data.dice.mean(),color=COLORS[1],ls='--',label=f'Trung bình {data.dice.mean():.3f}')
axes[0].axvline(data.dice.median(),color='#b16c1b',ls=':',label=f'Trung vị {data.dice.median():.3f}')
axes[0].set(xlabel='Dice từng ảnh',ylabel='Số ảnh',title='Phân bố trên Test lịch sử (402 ảnh)')
axes[0].legend(fontsize=9)
axes[1].scatter(data.recall,data.precision,s=13,alpha=.45,c=COLORS[0])
axes[1].set(xlabel='Recall từng ảnh',ylabel='Precision từng ảnh',xlim=(0,1.02),ylim=(0,1.02),title='Bỏ sót và dự đoán thừa')
save(fig, 'phan-bo-test-standard', [str(csv.relative_to(ROOT))])

prep = UltrasoundPreprocessor()
for image_name, fig_name in [('159.JPG','phan-doan-test-khop-cao'),('1295.JPG','phan-doan-test-bo-sot')]:
    row = data[data.image_path.str.endswith('/'+image_name)].iloc[0]
    image_path = resolve_dataset_path(ROOT,row.image_path)
    target_path = resolve_dataset_path(ROOT,row.ground_truth_path)
    image = cv2.imdecode(np.frombuffer(image_path.read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)
    target = cv2.imdecode(np.frombuffer(target_path.read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)
    image512,_ = prep.letterbox_resize(image)
    target512,_ = prep.letterbox_resize((target>0).astype(np.uint8),is_mask=True)
    prediction = cv2.imdecode(np.frombuffer((ROOT/row.prediction_path).read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)>0
    assert prediction.shape == target512.shape == (512,512)
    truth = target512>0
    tp = int(np.sum(truth & prediction));fp = int(np.sum(~truth & prediction));fn=int(np.sum(truth & ~prediction))
    assert (tp,fp,fn)==(int(row.tp),int(row.fp),int(row.fn)), 'Archived prediction does not match recorded metrics'
    overlay=np.repeat((image512/255.0)[...,None],3,axis=2)
    for mask,color in [(truth&prediction,[.15,.72,.65]),(~truth&prediction,[1,.6,.1]),(truth&~prediction,[.66,.4,.85])]:
        overlay[mask]=.55*overlay[mask]+.45*np.array(color)
    fig,axes=plt.subplots(2,2,figsize=(6.3,6.5))
    for ax,arr,title in zip(axes.flatten(),[image512,target512,prediction,overlay],['Ảnh đầu vào letterbox','Mask tham chiếu','Dự đoán đã lưu','TP xanh / FP cam / FN tím']):
        ax.imshow(arr,cmap='gray',vmin=0,vmax=1 if arr.dtype==bool else None)
        ax.set_title(title,fontsize=9);ax.axis('off')
    fig.suptitle(f'Standard U-Net · Test lịch sử · {image_name}\nDice={row.dice:.6f}',fontsize=10)
    save(fig,fig_name,[row.image_path,row.ground_truth_path,row.prediction_path,str(csv.relative_to(ROOT))])

image = cv2.imdecode(np.frombuffer((ROOT/'dataset/2d/images/159.JPG').read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)
letterbox,_=prep.letterbox_resize(image)
enhanced=prep.clahe.apply(letterbox)
raw_mask = cv2.imdecode(np.frombuffer((ROOT/'dataset/2d/masks/159_binary.PNG').read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)
mask512,_ = prep.letterbox_resize((raw_mask>0).astype(np.uint8),is_mask=True)
fig,axes=plt.subplots(2,2,figsize=(6.3,6.3))
for ax,arr,title in zip(axes.flatten(),[image,letterbox,enhanced,mask512*255],['Ảnh xám nguồn','Letterbox 512×512','CLAHE: clip 2, grid 8×8','Mask đồng bộ, nearest']):
    ax.imshow(arr,cmap='gray',vmin=0,vmax=255);ax.set_title(title,fontsize=10);ax.axis('off')
save(fig,'tien-xu-ly-thuc-te',['dataset/2d/images/159.JPG','dataset/2d/masks/159_binary.PNG','backend/services/preprocessor.py'])

(OUT/'manifest.json').write_text(json.dumps({'generated_from_existing_artifacts':True,'new_inference_performed':False,
    'checkpoint_for_test_panels':'417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d',
    'privacy_visual_check':'159.JPG and 1295.JPG visually inspected; no names, birth dates, patient IDs visible in the selected pixels; source authorization remains to be verified before external publication',
    'figures':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Generated {len(manifest)} paired PNG/SVG figures from archived data.')
