"""
Download sample disease images from Wikimedia Commons into the correct folder
structure for PlantDoc example images display.
Run once: python download_disease_images.py
"""
import os
import time
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(BASE_DIR, 'static', 'disease pics',
                    'Plant_leave_diseases_dataset_without_augmentation')

DISEASE_QUERIES = {
    'Apple___Apple_scab': 'Apple scab Venturia inaequalis',
    'Apple___Black_rot': 'Apple black rot Botryosphaeria',
    'Apple___Cedar_apple_rust': 'Cedar apple rust Gymnosporangium',
    'Apple___healthy': 'Apple leaf healthy',
    'Blueberry___healthy': 'Blueberry plant healthy leaf',
    'Cherry_(including_sour)___Powdery_mildew': 'Cherry powdery mildew',
    'Cherry_(including_sour)___healthy': 'Cherry tree leaf healthy',
    'Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot': 'Corn gray leaf spot Cercospora',
    'Corn_(maize)___Common_rust_': 'Maize common rust Puccinia',
    'Corn_(maize)___Northern_Leaf_Blight': 'Corn northern leaf blight',
    'Corn_(maize)___healthy': 'Maize corn leaf healthy',
    'Grape___Black_rot': 'Grape black rot disease',
    'Grape___Esca_(Black_Measles)': 'Grape esca disease grapevine',
    'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)': 'Grape leaf blight',
    'Grape___healthy': 'Grape vine leaf healthy',
    'Orange___Haunglongbing_(Citrus_greening)': 'Citrus greening disease huanglongbing',
    'Peach___Bacterial_spot': 'Peach bacterial spot',
    'Peach___healthy': 'Peach tree leaf healthy',
    'Pepper,_bell___Bacterial_spot': 'Pepper bacterial spot disease',
    'Pepper,_bell___healthy': 'Bell pepper plant leaf',
    'Potato___Early_blight': 'Potato early blight Alternaria',
    'Potato___Late_blight': 'Potato late blight Phytophthora',
    'Potato___healthy': 'Potato plant healthy',
    'Raspberry___healthy': 'Raspberry leaf healthy',
    'Soybean___healthy': 'Soybean plant leaf',
    'Squash___Powdery_mildew': 'Squash powdery mildew',
    'Strawberry___Leaf_scorch': 'Strawberry leaf scorch',
    'Strawberry___healthy': 'Strawberry plant leaf',
    'Tomato___Bacterial_spot': 'Tomato bacterial spot',
    'Tomato___Early_blight': 'Tomato early blight',
    'Tomato___Late_blight': 'Tomato late blight',
    'Tomato___Leaf_Mold': 'Tomato leaf mold',
    'Tomato___Septoria_leaf_spot': 'Tomato septoria leaf spot',
    'Tomato___Spider_mites Two-spotted_spider_mite': 'Spider mite Tetranychus urticae',
    'Tomato___Target_Spot': 'Tomato target spot Corynespora',
    'Tomato___Tomato_Yellow_Leaf_Curl_Virus': 'Tomato yellow leaf curl virus',
    'Tomato___Tomato_mosaic_virus': 'Tomato mosaic virus',
    'Tomato___healthy': 'Tomato plant leaf healthy',
}

HEADERS = {'User-Agent': 'PlantDocApp/1.0 (educational plant disease detection)'}
IMAGES_PER_DISEASE = 3
THUMB_WIDTH = 400  # Use thumbnails to avoid rate limits


def search_wikimedia(query, num=10):
    """Search Wikimedia Commons for images. Returns list of file titles."""
    url = 'https://commons.wikimedia.org/w/api.php'
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': query,
        'srnamespace': 6,
        'srlimit': num,
        'format': 'json'
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        hits = r.json().get('query', {}).get('search', [])
        return [h['title'] for h in hits
                if h['title'].lower().endswith(('.jpg', '.jpeg', '.png'))]
    except Exception as e:
        print(f'  Search error: {e}')
        return []


def get_thumb_urls(titles, width=THUMB_WIDTH):
    """Batch-resolve file titles to thumbnail URLs."""
    if not titles:
        return []
    url = 'https://commons.wikimedia.org/w/api.php'
    params = {
        'action': 'query',
        'titles': '|'.join(titles[:10]),  # max 10 per request
        'prop': 'imageinfo',
        'iiprop': 'url|thumburl|size',
        'iiurlwidth': width,
        'format': 'json'
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        pages = r.json().get('query', {}).get('pages', {})
        result = []
        for page in pages.values():
            info = (page.get('imageinfo') or [{}])[0]
            thumb = info.get('thumburl') or info.get('url', '')
            w = info.get('width', 0)
            h = info.get('height', 0)
            if thumb and w >= 200 and h >= 200:
                result.append(thumb)
        return result
    except Exception as e:
        print(f'  Thumb URL error: {e}')
        return []


def download_image(img_url, dest_path, retries=3):
    """Download image from URL to dest_path."""
    for attempt in range(retries):
        try:
            r = requests.get(img_url, headers=HEADERS, timeout=30, stream=True)
            if r.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f'  Rate limited, waiting {wait}s...')
                time.sleep(wait)
                continue
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            size = os.path.getsize(dest_path)
            if size > 5000:
                return True
            else:
                os.remove(dest_path)
                return False
        except Exception as e:
            print(f'  Download error (attempt {attempt+1}): {e}')
            if os.path.exists(dest_path):
                os.remove(dest_path)
            time.sleep(3)
    return False


def main():
    total = len(DISEASE_QUERIES)
    success_count = 0
    fail_count = 0

    print(f'Downloading sample images for {total} disease classes...\n')

    for idx, (disease, query) in enumerate(DISEASE_QUERIES.items(), 1):
        folder = os.path.join(DEST, disease)
        os.makedirs(folder, exist_ok=True)

        existing = [f for f in os.listdir(folder)
                    if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if len(existing) >= IMAGES_PER_DISEASE:
            success_count += 1
            print(f'[{idx}/{total}] SKIP {disease} ({len(existing)} images already exist)')
            continue

        need = IMAGES_PER_DISEASE - len(existing)
        print(f'[{idx}/{total}] {disease}')

        # Step 1: search for titles
        titles = search_wikimedia(query, num=15)
        time.sleep(1)  # polite delay after search

        if not titles:
            print(f'  No results found, trying simpler query...')
            # Try a simpler fallback query (just the crop name)
            plant = disease.split('___')[0].replace('_', ' ').replace('(', '').replace(')', '')
            titles = search_wikimedia(f'{plant} plant leaf disease', num=10)
            time.sleep(1)

        if not titles:
            print(f'  WARNING: No images found for {disease}')
            fail_count += 1
            continue

        # Step 2: get thumbnail URLs (batch request)
        thumb_urls = get_thumb_urls(titles[:10])
        time.sleep(1)

        # Step 3: download
        saved = 0
        for thumb_url in thumb_urls:
            if saved >= need:
                break
            ext = '.jpg' if 'jpg' in thumb_url.lower() or 'jpeg' in thumb_url.lower() else '.png'
            filename = f'sample_{len(existing) + saved + 1}{ext}'
            dest_path = os.path.join(folder, filename)
            print(f'  Downloading {filename}...')
            if download_image(thumb_url, dest_path):
                saved += 1
                size_kb = os.path.getsize(dest_path) // 1024
                print(f'  Saved {filename} ({size_kb}KB)')
            time.sleep(2)  # polite delay between downloads

        if saved > 0:
            success_count += 1
            print(f'  OK: {saved} image(s) saved')
        else:
            fail_count += 1
            print(f'  WARNING: Failed to download images for {disease}')

        time.sleep(2)  # delay between diseases

    print(f'\n{"="*50}')
    print(f'Done! {success_count}/{total} diseases have images')
    if fail_count > 0:
        print(f'{fail_count} diseases had no images found - these will show "no examples" in the UI')
    print(f'\nImages saved to:\n  {DEST}')


if __name__ == '__main__':
    main()
