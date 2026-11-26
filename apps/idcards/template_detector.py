import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from io import BytesIO
from PIL import Image, ImageFilter

FIELD_SPECS = [
    ('photo_number', 'Photo No', ['photo number', 'photo no', 'pic no', 'photo id']),
    ('father_name', 'Father Name', ["father's name", 'father name', 'f name', 'f.name', 'guardian name', 'guardian']),
    ('mother_name', 'Mother Name', ["mother's name", 'mother name', 'm name', 'm.name']),
    ('roll_number', 'Roll No', ['roll number', 'roll no', 'roll #', 'roll']),
    ('admission_number', 'Admission No', ['admission number', 'admission no', 'adm number', 'adm no', 'registration no', 'reg no', 'student id', 'id no']),
    ('dob', 'Date of Birth', ['date of birth', 'birth date', 'd.o.b', 'dob']),
    ('blood_group', 'Blood Group', ['blood group', 'b.group', 'b group', 'blood', 'b.g']),
    ('emergency_contact', 'Mobile No', ['mobile number', 'mobile no', 'mob number', 'mob no', 'phone number', 'phone no', 'contact no', 'emergency contact', 'mobile', 'phone', 'mob', 'contact', 'tel']),
    ('address', 'Address', ['residential address', 'permanent address', 'address', 'addr']),
    ('class_section', 'Class', ['class & sec', 'class and section', 'class/sec', 'class']),
    ('section_name', 'Section', ['section', 'sec']),
    ('session_name', 'Session', ['academic session', 'session']),
    ('full_name', 'Student Name', ['student name', 'full name', 'candidate name', 'pupil name', 'name']),
]

TOKEN_MAP = {
    'name': ('full_name', 'Student Name'),
    'full_name': ('full_name', 'Student Name'),
    'student_name': ('full_name', 'Student Name'),
    'first_name': ('first_name', 'First Name'),
    'class': ('class_section', 'Class'),
    'class_name': ('class_name', 'Class'),
    'class_section': ('class_section', 'Class'),
    'section': ('section_name', 'Section'),
    'section_name': ('section_name', 'Section'),
    'roll': ('roll_number', 'Roll No'),
    'roll_no': ('roll_number', 'Roll No'),
    'roll_number': ('roll_number', 'Roll No'),
    'admission': ('admission_number', 'Admission No'),
    'adm_no': ('admission_number', 'Admission No'),
    'admission_number': ('admission_number', 'Admission No'),
    'id': ('admission_number', 'Admission No'),
    'father_name': ('father_name', 'Father Name'),
    'f_name': ('father_name', 'Father Name'),
    'guardian': ('father_name', 'Father Name'),
    'mother_name': ('mother_name', 'Mother Name'),
    'm_name': ('mother_name', 'Mother Name'),
    'dob': ('dob', 'Date of Birth'),
    'date_of_birth': ('dob', 'Date of Birth'),
    'blood': ('blood_group', 'Blood Group'),
    'blood_group': ('blood_group', 'Blood Group'),
    'phone': ('emergency_contact', 'Mobile No'),
    'mobile': ('emergency_contact', 'Mobile No'),
    'mob_no': ('emergency_contact', 'Mobile No'),
    'emergency_contact': ('emergency_contact', 'Mobile No'),
    'address': ('address', 'Address'),
    'session': ('session_name', 'Session'),
    'session_name': ('session_name', 'Session'),
    'photo_no': ('photo_number', 'Photo No'),
    'photo_number': ('photo_number', 'Photo No'),
    'school_name': ('school_name', 'School Name'),
    'principal_name': ('principal_name', 'Principal Name'),
}

_WIN_OCR_SCRIPT = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
function Await($WinRtTask, $ResultType) {
    $netTask = $asTaskGeneric.MakeGenericMethod($ResultType).Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
[Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime] | Out-Null
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($env:OCR_IMAGE_PATH)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $engine) {
    $lang = [Windows.Globalization.Language]::new('en-US')
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
}
$res = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$lines = @()
foreach ($line in $res.Lines) {
    $words = @()
    foreach ($w in $line.Words) {
        $r = $w.BoundingRect
        $words += @{
            text = $w.Text
            x = [Math]::Round($r.X, 1)
            y = [Math]::Round($r.Y, 1)
            w = [Math]::Round($r.Width, 1)
            h = [Math]::Round($r.Height, 1)
        }
    }
    $lines += @{ text = $line.Text; words = $words }
}
$lines | ConvertTo-Json -Depth 4 -Compress
"""


def _normalize_label(text):
    """Normalize punctuation and spacing so OCR quirks like F.Name / D.O.B match reliably."""
    cleaned = re.sub(r'[._\-:=]+', ' ', (text or '').lower())
    return re.sub(r'\s+', ' ', cleaned).strip()


def _sample_text_color(pil_img, x_px, y_px, w_px, h_px):
    """Sample darkest ink pixels inside a bounding box, defaulting to crisp slate-dark."""
    try:
        x0 = max(0, int(x_px))
        y0 = max(0, int(y_px))
        x1 = min(pil_img.width, max(x0 + 1, int(x_px + w_px)))
        y1 = min(pil_img.height, max(y0 + 1, int(y_px + h_px)))
        crop = pil_img.crop((x0, y0, x1, y1)).convert('RGB')
        pixels = list(crop.getdata())
        if not pixels:
            return '#111827'
        # Measure corner brightness to avoid returning pure white/light background colors
        darkest = min(pixels, key=lambda rgb: 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2])
        luminance = 0.299 * darkest[0] + 0.587 * darkest[1] + 0.114 * darkest[2]
        if luminance > 180:
            return '#ffffff'
        return f'#{darkest[0]:02x}{darkest[1]:02x}{darkest[2]:02x}'
    except Exception:
        return '#111827'


def _run_windows_ocr(pil_img):
    """Run Windows built-in WinRT OCR on an upscaled temporary PNG and return line dicts."""
    if sys.platform != 'win32':
        return []

    scale = 2.0 if pil_img.width < 900 else 1.0
    ocr_img = pil_img.convert('RGB')
    if scale > 1.0:
        ocr_img = ocr_img.resize(
            (int(ocr_img.width * scale), int(ocr_img.height * scale)),
            Image.Resampling.LANCZOS,
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name
        ocr_img.save(tmp_path, format='PNG')

        env = os.environ.copy()
        env['OCR_IMAGE_PATH'] = tmp_path
        proc = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', _WIN_OCR_SCRIPT],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        raw = json.loads(proc.stdout.strip())
        if isinstance(raw, dict):
            raw = [raw]

        normalized_lines = []
        for line in raw:
            words = []
            for word in line.get('words') or []:
                words.append({
                    'text': word.get('text', ''),
                    'x': float(word.get('x', 0)) / scale,
                    'y': float(word.get('y', 0)) / scale,
                    'w': float(word.get('w', 0)) / scale,
                    'h': float(word.get('h', 0)) / scale,
                })
            if words:
                normalized_lines.append({'text': line.get('text', ''), 'words': words})
        return normalized_lines
    except Exception:
        return []
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _match_field_alias(phrase):
    """Match a short word span against FIELD_SPECS longest-first."""
    norm = _normalize_label(phrase)
    if not norm:
        return None
    for field_key, display_label, aliases in FIELD_SPECS:
        for alias in aliases:
            alias_norm = _normalize_label(alias)
            if norm == alias_norm or norm.startswith(f'{alias_norm} '):
                return (field_key, display_label)
    return None


def _extract_fields_from_ocr_lines(ocr_lines, pil_img):
    """Inspect OCR word bounding boxes along each line to place values beside labels."""
    w_total = float(pil_img.width)
    h_total = float(pil_img.height)
    detected = []
    seen_keys = set()

    for line in ocr_lines:
        words = sorted(line['words'], key=lambda item: item['x'])
        idx = 0
        line_matches = []

        while idx < len(words):
            matched = None
            matched_end = idx

            # Try 3-word, 2-word, and 1-word label spans (also skip school title lines)
            for span in (3, 2, 1):
                if idx + span > len(words):
                    continue
                candidate = ' '.join(words[j]['text'] for j in range(idx, idx + span))
                candidate_lower = candidate.lower()
                if 'school' in candidate_lower or 'high' in candidate_lower or 'academy' in candidate_lower:
                    continue
                hit = _match_field_alias(candidate)
                if hit:
                    matched = hit
                    matched_end = idx + span - 1
                    break

            if not matched:
                idx += 1
                continue

            field_key, display_label = matched
            start_x = words[idx]['x']
            end_x = words[matched_end]['x'] + words[matched_end]['w']
            top_y = min(words[j]['y'] for j in range(idx, matched_end + 1))
            box_h = max(words[j]['h'] for j in range(idx, matched_end + 1))

            # Consume immediate trailing separator token ("-", ":", "=", "–") on the same line
            next_idx = matched_end + 1
            if next_idx < len(words) and re.fullmatch(r'[\-–—:=.]+', words[next_idx]['text'].strip()):
                end_x = max(end_x, words[next_idx]['x'] + words[next_idx]['w'])
                next_idx += 1

            # Avoid capturing same field twice unless missing
            if field_key not in seen_keys:
                seen_keys.add(field_key)
                ink = _sample_text_color(pil_img, start_x, top_y, end_x - start_x, box_h)
                # Switch white-banner headers onto dark slate for dark text contrast inside light card bodies
                if ink == '#ffffff' and top_y > h_total * 0.3:
                    ink = '#111827'
                line_matches.append({
                    'field_key': field_key,
                    'display_label': display_label,
                    'label_start_x': start_x,
                    'value_x': end_x + max(6.0, w_total * 0.015),
                    'y': top_y,
                    'h': box_h,
                    'color': ink,
                })

            idx = max(next_idx, idx + 1)

        # Compute clean max width before next column label on the same row
        for pos_idx, match in enumerate(line_matches):
            next_col_x = line_matches[pos_idx + 1]['label_start_x'] - w_total * 0.02 if pos_idx + 1 < len(line_matches) else w_total * 0.94
            x_pct = round(min(84.0, (match['value_x'] / w_total) * 100.0), 2)
            y_pct = round(max(4.0, min(92.0, (match['y'] / h_total) * 100.0)), 2)
            max_w_pct = round(max(12.0, ((next_col_x - match['value_x']) / w_total) * 100.0), 2)
            font_size_pct = round(max(2.3, min(4.2, (match['h'] / h_total) * 95.0)), 2)

            detected.append({
                'id': f"field_{match['field_key']}_{len(detected) + 1}",
                'fieldKey': match['field_key'],
                'label': match['display_label'],
                'xPct': x_pct,
                'yPct': y_pct,
                'maxWidthPct': max_w_pct,
                'fontSizePct': font_size_pct,
                'color': match['color'] if match['color'] != '#ffffff' else '#111827',
                'fontWeight': 700,
                'align': 'left',
            })

    return detected


def _detect_photo_box_pillow(pil_img, ocr_lines):
    """Detect an enclosed portrait rectangular frame on raster ID templates."""
    try:
        target_w = 220
        scale = target_w / float(pil_img.width)
        target_h = max(120, int(pil_img.height * scale))
        gray = pil_img.convert('L').resize((target_w, target_h), Image.Resampling.BILINEAR)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        px = edges.load()

        # Look for contiguous horizontal top/bottom edges and vertical left/right edges
        y_min = int(target_h * 0.14)
        y_max = int(target_h * 0.68)
        x_min = int(target_w * 0.10)
        x_max = int(target_w * 0.90)

        h_lines = {}
        for y in range(y_min, y_max):
            run_start = None
            for x in range(x_min, x_max):
                if px[x, y] > 32:
                    if run_start is None:
                        run_start = x
                else:
                    if run_start is not None and (x - run_start) >= int(target_w * 0.18):
                        h_lines.setdefault(y, []).append((run_start, x - 1))
                    run_start = None
            if run_start is not None and (x_max - run_start) >= int(target_w * 0.18):
                h_lines.setdefault(y, []).append((run_start, x_max - 1))

        best_box = None
        best_score = 0
        y_coords = sorted(h_lines.keys())

        for i, top_y in enumerate(y_coords):
            for x0, x1 in h_lines[top_y]:
                box_w = x1 - x0 + 1
                if box_w < target_w * 0.18 or box_w > target_w * 0.56:
                    continue
                for bot_y in y_coords[i + 1:]:
                    box_h = bot_y - top_y + 1
                    if box_h < target_h * 0.16:
                        continue
                    if box_h > target_h * 0.48:
                        break
                    aspect = box_w / float(box_h)
                    if aspect < 0.62 or aspect > 1.25:
                        continue

                    # Confirm bottom edge overlaps horizontally
                    matched_bottom = any(
                        abs(bx0 - x0) <= 6 and abs(bx1 - x1) <= 6
                        for bx0, bx1 in h_lines[bot_y]
                    )
                    if not matched_bottom:
                        continue

                    # Verify left & right vertical edge continuity around x0 and x1
                    left_hits = sum(
                        1 for yy in range(top_y, bot_y + 1)
                        if any(px[max(0, min(target_w - 1, x0 + dx)), yy] > 30 for dx in (-2, -1, 0, 1, 2))
                    )
                    right_hits = sum(
                        1 for yy in range(top_y, bot_y + 1)
                        if any(px[max(0, min(target_w - 1, x1 + dx)), yy] > 30 for dx in (-2, -1, 0, 1, 2))
                    )
                    vert_ratio = (left_hits + right_hits) / float(2 * box_h)
                    if vert_ratio < 0.62:
                        continue

                    # Skip boxes sitting over heavy OCR title text
                    img_x0, img_y0 = x0 / scale, top_y / scale
                    img_x1, img_y1 = x1 / scale, bot_y / scale
                    word_hits = sum(
                        1
                        for line in ocr_lines
                        for word in line['words']
                        if (img_x0 - 4 <= word['x'] + word['w'] * 0.5 <= img_x1 + 4)
                        and (img_y0 - 4 <= word['y'] + word['h'] * 0.5 <= img_y1 + 4)
                    )
                    if word_hits > 1:
                        continue

                    score = vert_ratio * 100.0 + box_w * 0.25
                    if score > best_score:
                        best_score = score
                        best_box = {
                            'xPct': round((x0 / target_w) * 100.0, 2),
                            'yPct': round((top_y / target_h) * 100.0, 2),
                            'widthPct': round((box_w / target_w) * 100.0, 2),
                            'heightPct': round((box_h / target_h) * 100.0, 2),
                            'borderRadius': 4,
                        }

        return best_box
    except Exception:
        return None


def detect_raster_template_fields(file_obj):
    """Detect aspect ratio, student fields, and photo placeholder box from a raster ID template."""
    data = file_obj.read()
    pil_img = Image.open(BytesIO(data))
    width, height = pil_img.size
    aspect_ratio = round(width / float(height), 4) if height else 0.65
    layout = 'vertical' if height > width else 'horizontal'

    ocr_lines = _run_windows_ocr(pil_img)
    fields = _extract_fields_from_ocr_lines(ocr_lines, pil_img)
    photo_box = _detect_photo_box_pillow(pil_img, ocr_lines)

    return {
        'fileType': 'raster',
        'width': width,
        'height': height,
        'aspectRatio': aspect_ratio,
        'layout': layout,
        'photoBox': photo_box,
        'fields': fields,
    }


def _parse_svg_length(raw, fallback):
    """Parse SVG numeric length stripping units like px."""
    if not raw:
        return fallback
    match = re.search(r'[\d.]+', str(raw))
    return float(match.group(0)) if match else fallback


def detect_svg_template_fields(svg_text):
    """Fallback backend parser for SVG viewBox & token placeholders."""
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return {
            'fileType': 'svg',
            'aspectRatio': 0.65,
            'layout': 'vertical',
            'photoBox': None,
            'fields': [],
        }

    view_box = root.attrib.get('viewBox') or root.attrib.get('viewbox')
    if view_box:
        nums = [float(val) for val in re.split(r'[\s,]+', view_box.strip()) if val]
        vb_w, vb_h = (nums[2], nums[3]) if len(nums) >= 4 else (340.0, 520.0)
    else:
        vb_w = _parse_svg_length(root.attrib.get('width'), 340.0)
        vb_h = _parse_svg_length(root.attrib.get('height'), 520.0)

    aspect_ratio = round(vb_w / float(vb_h), 4) if vb_h else 0.65
    layout = 'vertical' if vb_h > vb_w else 'horizontal'

    return {
        'fileType': 'svg',
        'width': vb_w,
        'height': vb_h,
        'aspectRatio': aspect_ratio,
        'layout': layout,
        'photoBox': None,
        'fields': [],
    }

