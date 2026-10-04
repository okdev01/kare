import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QDesktopServices, QImageReader, QPixmap
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QSpinBox, QTableWidgetItem)

from desktop import Shell, button, label, card, table, run
from engine import Settings, inspect, export_batch


class Window(Shell):
    def __init__(self, folder):
        super().__init__("Kare", "Fotoğraflarını hazırla.\nOrijinalleri sakla.", "Bir klasör dolusu, tek ayar.",
                         "Fotoğrafları topluca küçült, döndür veya farklı formatta kaydet.", "Fotoğraf atölyesi")
        self.folder = folder
        self.resize(1140, 830)
        self.setMinimumHeight(800)
        self.sources = []
        self.last_output = None
        self.settings_data = Settings()
        toolbar = QHBoxLayout()
        toolbar.addWidget(button("Fotoğraf ekle", self.choose_files, True))
        toolbar.addWidget(button("Listeyi temizle", self.clear))
        toolbar.addStretch()
        self.file_count = label("0 fotoğraf", "muted")
        toolbar.addWidget(self.file_count)
        self.body.addLayout(toolbar)
        top = QHBoxLayout()
        self.grid = table(["Fotoğraf", "Boyut", "Biçim"])
        self.grid.itemSelectionChanged.connect(self.preview_selected)
        top.addWidget(self.grid, 3)
        preview_card, preview_layout = card()
        preview_layout.addWidget(label("ÖNİZLEME", "eyebrow"))
        self.image = QLabel("Fotoğraf seçildiğinde\nburada görünür")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumWidth(225)
        self.image.setFixedHeight(160)
        self.image.setStyleSheet("background: #0e192a; border-radius: 10px; color: #a6b5cf;")
        preview_layout.addWidget(self.image, 1)
        self.image_caption = label("Orijinal dosya değişmez.", "muted", True)
        preview_layout.addWidget(self.image_caption)
        top.addWidget(preview_card, 2)
        self.body.addLayout(top, 1)
        settings_card, settings_layout = card()
        settings_layout.addWidget(label("Nasıl kaydedilsin?", "eyebrow"))
        fields = QGridLayout()
        self.width, self.height = QSpinBox(), QSpinBox()
        for spin in (self.width, self.height):
            spin.setRange(16,12000)
            spin.setValue(1920)
            spin.setSuffix(" px")
        self.format = QComboBox()
        self.format.addItems(["JPEG", "PNG", "WEBP"])
        self.quality = QSpinBox()
        self.quality.setRange(1,100)
        self.quality.setValue(90)
        self.format.currentTextChanged.connect(lambda text: self.quality.setEnabled(text != "PNG"))
        self.rotation = QComboBox()
        self.rotation.addItems(["Döndürme yok", "90° sağa", "180°", "90° sola"])
        for col, (title, field) in enumerate([("En fazla genişlik",self.width), ("En fazla yükseklik",self.height),
                                            ("Format",self.format), ("Kalite",self.quality), ("Döndür",self.rotation)]):
            fields.addWidget(label(title,"muted"),0,col)
            fields.addWidget(field,1,col)
        settings_layout.addLayout(fields)
        settings_layout.addWidget(label("En-boy oranı korunur; küçük fotoğraflar büyütülmez. Çıktılardan konum ve kamera bilgileri kaldırılır.","muted",True))
        self.body.addWidget(settings_card)
        destination = QHBoxLayout()
        self.output = QLineEdit()
        self.output.setPlaceholderText("Yeni fotoğrafların kaydedileceği ayrı klasör")
        destination.addWidget(self.output,1)
        destination.addWidget(button("Çıktı klasörü", self.choose_output))
        self.body.addLayout(destination)
        actions = QHBoxLayout()
        self.open_button = button("Çıktıları aç", self.open_output)
        self.open_button.setEnabled(False)
        actions.addWidget(self.open_button)
        actions.addStretch()
        self.export_button = button("Fotoğrafları kaydet", self.export, True)
        self.export_button.setEnabled(False)
        actions.addWidget(self.export_button)
        self.body.addLayout(actions)
        self.finish_layout()
        self.status.setText("JPEG, PNG, WebP, BMP ve tek sayfalı TIFF. Bir seferde en fazla 200 fotoğraf.")

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self,"Fotoğrafları seç","","Fotoğraflar (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)")
        if paths:
            combined = list(dict.fromkeys(self.sources + paths))
            if len(combined)>200:
                self.status.setText("En fazla 200 fotoğraf seçebilirsiniz.")
                return
            self.work(lambda: self.inspect_paths(combined), self.loaded)

    @staticmethod
    def inspect_paths(paths):
        result=[]
        for path in paths:
            try: result.append((path,inspect(path),""))
            except Exception as exc: result.append((path,None,str(exc)))
        return result

    def loaded(self, result):
        self.sources = [p for p, info, error in result if info]
        valid = [(p, info) for p, info, error in result if info]
        self.grid.setRowCount(len(valid))
        for row,(path,info) in enumerate(valid):
            for col,text in enumerate([Path(path).name, f'{info["width"]} × {info["height"]}',info["format"]]):
                self.grid.setItem(row,col,QTableWidgetItem(text))
        self.file_count.setText(f"{len(valid)} fotoğraf")
        self.export_button.setEnabled(bool(valid))
        failures=[e for p,i,e in result if e]
        self.status.setText(f"{len(valid)} fotoğraf hazır." + (f" {len(failures)} dosya atlandı: {failures[0]}" if failures else ""))
        if valid: self.grid.selectRow(0)

    def preview_selected(self):
        row=self.grid.currentRow()
        if not 0<=row<len(self.sources): return
        reader=QImageReader(self.sources[row])
        reader.setAutoTransform(True)
        size=reader.size()
        if size.isValid(): reader.setScaledSize(size.scaled(QSize(500,260),Qt.AspectRatioMode.KeepAspectRatio))
        image=reader.read()
        if not image.isNull():
            pix=QPixmap.fromImage(image).scaled(270,150,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            self.image.setPixmap(pix)
        self.image_caption.setText(Path(self.sources[row]).name)

    def clear(self):
        self.sources=[]
        self.grid.setRowCount(0)
        self.image.clear()
        self.image.setText("Fotoğraf ekleyerek başla")
        self.file_count.setText("0 fotoğraf")
        self.export_button.setEnabled(False)

    def choose_output(self):
        path=QFileDialog.getExistingDirectory(self,"Çıktı klasörü seç")
        if path: self.output.setText(path)

    def export(self):
        if not self.output.text().strip():
            self.status.setText("Önce ayrı bir çıktı klasörü seçin.")
            return
        settings=Settings(self.width.value(),self.height.value(),self.format.currentText(),self.quality.value(),[0,90,180,270][self.rotation.currentIndex()])
        sources=list(self.sources)
        output=self.output.text().strip()
        self.work(lambda:export_batch(sources,output,settings),self.exported)

    def exported(self,results):
        success=[r for r in results if r["ok"]]
        failures=[r for r in results if not r["ok"]]
        if success:
            self.last_output=Path(success[0]["output"]).parent
            self.open_button.setEnabled(True)
        self.status.setText(f"{len(success)} fotoğraf kaydedildi. {len(failures)} dosya atlandı." +
                            (" " + failures[0]["error"] if failures else " Orijinaller aynı yerde duruyor."))

    def open_output(self):
        if self.last_output: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output)))

    def seed_demo(self):
        from PIL import Image,ImageDraw
        root=self.folder/"fotoğraflar"
        root.mkdir()
        for i,name in enumerate(["Dağ yolu.jpg","Kıyı.png","Akşam.jpg"]):
            image=Image.new("RGB",(1200,800),(92+i*30,144-i*15,182-i*12))
            draw=ImageDraw.Draw(image)
            draw.ellipse((820,110,950,240),fill=(255,221,159))
            draw.polygon([(0,800),(0,540),(300,260),(620,680),(920,340),(1200,550),(1200,800)],fill=(35,70+i*10,90))
            draw.polygon([(0,800),(0,700),(440,420),(760,730),(1200,590),(1200,800)],fill=(21,46,54))
            image.save(root/name)
        self.loaded(self.inspect_paths([str(p) for p in sorted(root.iterdir())]))
        self.output.setText(str(self.folder/"Kare çıktıları"))
        self.status.setText("Örnek görünüm · Önizleme görselleri uygulama testi için çizildi.")

    def smoke(self):
        assert len(self.sources)==3
        output=self.folder/"Kare çıktıları"
        result=export_batch(self.sources,output,Settings(600,600))
        assert len(result)==3 and all(r["ok"] for r in result)
        assert all(max(r["width"],r["height"])<=600 for r in result)
        self.exported(result)
        assert self.open_button.isEnabled()
        return ["load and preview", "batch resize", "separate JPEG exports"]


if __name__=="__main__":
    sys.exit(run(Window,"Kare"))
