from google.appengine.api import images

from agar.image import Image, NdbImage
from agar.test import BaseTest


TEST_IMAGE_PATH = 'tests/media/appengine-noborder-120x30.jpg'


class ImageTest(BaseTest):
    def setUp(self):
        super(ImageTest, self).setUp()
        self.image_file = open(TEST_IMAGE_PATH)
        self.image_bytes = self.image_file.read()
        self.image_file.close()

    def test_create_with_data(self):
        image = Image.create(data=self.image_bytes, filename=TEST_IMAGE_PATH)
        self.assertIsNotNone(image.blob_info)
        self.assertEqual(Image.all().count(), 1)
        self.assertMemcacheItems(0)
        self.assertEqual(image.get_serving_url(), images.get_serving_url(image.blob_key))
        self.assertMemcacheItems(1)
        self.assertMemcacheHits(0)
        self.assertEqual(image.get_serving_url(), images.get_serving_url(image.blob_key))
        self.assertMemcacheHits(1)
        image2 = Image.create(data=self.image_bytes, filename=TEST_IMAGE_PATH)
        self.assertNotEqual(image.get_serving_url(), images.get_serving_url(image2.blob_key))
        self.assertMemcacheItems(1)
        self.assertMemcacheHits(2)
        self.assertEqual(image2.get_serving_url(), images.get_serving_url(image2.blob_key))
        self.assertMemcacheItems(2)
        self.assertMemcacheHits(2)

    def test_delete(self):
        image = Image.create(data=self.image_bytes, filename=TEST_IMAGE_PATH)
        self.assertIsNotNone(image.blob_info)
        blob_key = image.blob_key
        self.assertEqual(image.get_serving_url(), images.get_serving_url(blob_key))
        self.assertEqual(Image.all().count(), 1)
        image.delete()
        self.assertEqual(Image.all().count(), 0)
        #It doesn't appear that the blobstore test stub actually deletes blob_infos
#        self.assertEqual(images.get_serving_url(image.blob_key), None)
#        self.assertIsNone(blobstore.BlobInfo(blob_key))


class NdbImageTest(BaseTest):
    def setUp(self):
        super(NdbImageTest, self).setUp()
        self.image_file = open(TEST_IMAGE_PATH)
        self.image_bytes = self.image_file.read()
        self.image_file.close()

    def test_create_with_data(self):
        image = NdbImage.create(data=self.image_bytes, filename=TEST_IMAGE_PATH)
        self.assertMemcacheItems(0)
        self.assertEqual(image.get_serving_url(), images.get_serving_url(image.blob_key))
        self.assertMemcacheItems(1)
        self.assertMemcacheHits(0)
        self.assertEqual(image.get_serving_url(), images.get_serving_url(image.blob_key))
        self.assertMemcacheHits(1)
        image2 = Image.create(data=self.image_bytes, filename=TEST_IMAGE_PATH)
        self.assertNotEqual(image.get_serving_url(), images.get_serving_url(image2.blob_key))
        self.assertMemcacheItems(1)
        self.assertMemcacheHits(2)
        self.assertEqual(image2.get_serving_url(), images.get_serving_url(image2.blob_key))
        self.assertMemcacheItems(2)
        self.assertMemcacheHits(2)

    def test_delete(self):
            image = Image.create(data=self.image_bytes, filename=TEST_IMAGE_PATH)
            self.assertIsNotNone(image.blob_info)
            blob_key = image.blob_key
            self.assertEqual(image.get_serving_url(), images.get_serving_url(blob_key))
            self.assertEqual(Image.all().count(), 1)
            image.delete()
            self.assertEqual(Image.all().count(), 0)
            #It doesn't appear that the blobstore test stub actually deletes blob_infos
#            self.assertEqual(images.get_serving_url(image.blob_key), None)
#            self.assertIsNone(blobstore.BlobInfo(blob_key))
