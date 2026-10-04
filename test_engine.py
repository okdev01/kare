from pathlib import Path
import tempfile
import unittest
from PIL import Image
from engine import Settings, inspect, export_batch, export_one


class PhotoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/"photo.png"
        Image.new("RGBA",(100,50),(255,0,0,0)).save(self.source)
        self.output=self.root/"output"

    def test_resize_preserves_aspect_and_original(self):
        before=self.source.read_bytes()
        result=export_one(self.source,self.output,Settings(40,40))
        self.assertEqual((result["width"],result["height"]),(40,20))
        self.assertEqual(before,self.source.read_bytes())

    def test_no_upscale(self):
        result=export_one(self.source,self.output,Settings(1000,1000))
        self.assertEqual(result["width"],100)

    def test_alpha_flattens_to_white_for_jpeg(self):
        result=export_one(self.source,self.output,Settings())
        with Image.open(result["output"]) as image:
            self.assertEqual(image.mode,"RGB")
            self.assertTrue(all(c>250 for c in image.getpixel((0,0))))

    def test_png_keeps_alpha_and_rotation(self):
        result=export_one(self.source,self.output,Settings(1000,1000,"PNG",90,90))
        with Image.open(result["output"]) as image:
            self.assertEqual(image.size,(50,100))
            self.assertEqual(image.getpixel((0,0))[3],0)

    def test_duplicate_name_never_overwrites(self):
        a=export_one(self.source,self.output,Settings())
        before=Path(a["output"]).read_bytes()
        b=export_one(self.source,self.output,Settings())
        self.assertNotEqual(a["output"],b["output"])
        self.assertEqual(Path(a["output"]).read_bytes(),before)

    def test_same_folder_rejected_before_output(self):
        with self.assertRaises(ValueError): export_batch([self.source],self.root,Settings())
        self.assertEqual(len(list(self.root.iterdir())),1)

    def test_batch_continues_after_bad_file(self):
        bad=self.root/"bad.jpg"
        bad.write_text("not an image")
        results=export_batch([bad,self.source],self.output,Settings())
        self.assertFalse(results[0]["ok"])
        self.assertTrue(results[1]["ok"])

    def test_exif_orientation_and_metadata_removed(self):
        source=self.root/"oriented.jpg"
        exif=Image.Exif()
        exif[274]=6
        exif[315]="Private author"
        Image.new("RGB",(80,40),"red").save(source,exif=exif)
        self.assertEqual(inspect(source)["width"],40)
        result=export_one(source,self.output,Settings())
        with Image.open(result["output"]) as image:
            self.assertEqual(image.size,(40,80))
            self.assertEqual(len(image.getexif()),0)

    def test_animated_image_rejected(self):
        source=self.root/"animated.gif"
        Image.new("RGB",(30,30),"red").save(source,save_all=True,append_images=[Image.new("RGB",(30,30),"blue")])
        with self.assertRaises(ValueError): inspect(source)


if __name__=="__main__": unittest.main()
