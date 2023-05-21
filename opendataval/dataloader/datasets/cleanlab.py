"""Clean Lab data sets

Provides corrected test sets most common ML benchmark test sets: ImageNet, MNIST,
CIFAR-10, CIFAR-100, Caltech-256, QuickDraw, IMDB, Amazon Reviews, 20News, and AudioSet.
These data sets are NOT 100% perfect, nor are they intended to be.

References
----------
.. [1] C. G. Northcutt, A. Athalye, and J. Mueller,
    Pervasive Label Errors in Test Sets Destabilize Machine Learning Benchmarks
    arXiv.org, 2021. [Online]. Available: https://arxiv.org/abs/2103.14749.
"""
import glob
import tarfile

from torchvision.datasets import ImageNet

from opendataval.dataloader.datasets.imagesets import ResnetEmbeding, VisionAdapter
from opendataval.dataloader.register import Register, cache


def CleanLabImagenet(root: str, download: bool, **kwargs) -> ImageNet:
    """ImageNet constructor that downloads the CleanLab cleaned validation set.

     Parameters
     ----------
    cache_dir : str
             Directory to download cached files to.
         force_download : bool
             Whether to force a download of the data files.


     References
     ----------
     .. [1] C. G. Northcutt, A. Athalye, and J. Mueller,
         Pervasive Label Errors in Test Sets Destabilize Machine Learning Benchmarks
         arXiv.org, 2021. Available: https://arxiv.org/abs/2103.14749.
     .. [2] J. Deng, W. Dong, R. Socher, LJ Li, K. Li, and L. Fei-Fei,
         ImageNet: A large-scale hierarchical image database,
         Jun. 2009, doi: https://doi.org/10.1109/cvpr.2009.5206848.

     Returns
     -------
     ImageNet
         ImageNet validation data set with corrected labels by CleanLab
    """
    devkit_url = "https://image-net.org/data/ILSVRC/2012/ILSVRC2012_devkit_t12.tar.gz"
    _ = cache(devkit_url, root, force_download=download)

    imagenet_val_url = "https://image-net.org/data/ILSVRC/2012/ILSVRC2012_img_val.tar"
    tarpath = cache(imagenet_val_url, root, force_download=download)

    if next(glob.iglob("*.JPEG", root_dir=root), None) is None or download:
        tf = tarfile.open(tarpath)
        tf.extractall(root)  # specify which folder to extract to
        tf.close()

    return ImageNet(root=root, split="val", **kwargs)


imagenet = Register("imagenet", True, True)(VisionAdapter(CleanLabImagenet))
"""Vision Classification registered as ``"imagenet"``, from TorchVision."""

im_embed = Register("imagenet-embeddings", True, True)(ResnetEmbeding(CleanLabImagenet))
"""Vision Classification registered as ``"imagenet-embeddings"`` ResNet50 embeddings"""
