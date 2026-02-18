# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


MEDIA_CONTENT_TYPE_MAP = {
    'EXTERNAL_VIDEO': ('External Video', 'An externally hosted video.'),
    'IMAGE': ('Image', 'A Shopify-hosted image.'),
    'MODEL_3D': ('Model 3D', 'A 3d model.'),
    'VIDEO': ('Video', 'A Shopify-hosted video.'),
}


class MediaContentType(StatusAbstract):

    external_video = 'EXTERNAL_VIDEO'
    image = 'IMAGE'
    model_3d = 'MODEL_3D'
    video = 'VIDEO'

    @property
    def is_external_video(self):
        return self == self.external_video

    @property
    def is_image(self):
        return self == self.image

    @property
    def is_model_3d(self):
        return self == self.model_3d

    @property
    def is_video(self):
        return self == self.video

    @property
    def mapping(self):
        return MEDIA_CONTENT_TYPE_MAP
