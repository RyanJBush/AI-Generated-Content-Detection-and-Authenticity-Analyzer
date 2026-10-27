from PIL import Image

from litmus.ingestion import analyze_ingestion


def test_ingestion_real_fixtures(tmp_path):
    # Generate valid JPEG
    img_jpg = Image.new('RGB', (10, 10), color='red')
    path_jpg = tmp_path / "test.jpg"
    img_jpg.save(path_jpg, "JPEG")
    assert analyze_ingestion(str(path_jpg))["result"] == "supported"

    # Generate valid PNG
    img_png = Image.new('RGB', (10, 10), color='blue')
    path_png = tmp_path / "test.png"
    img_png.save(path_png, "PNG")
    assert analyze_ingestion(str(path_png))["result"] == "supported"

    # Generate valid WebP
    img_webp = Image.new('RGB', (10, 10), color='green')
    path_webp = tmp_path / "test.webp"
    img_webp.save(path_webp, "WebP")
    assert analyze_ingestion(str(path_webp))["result"] == "supported"
