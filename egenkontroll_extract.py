from pdfminer.high_level import extract_text
import pickle
import os
import json
import re

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded .env file")
except ImportError:
    print("python-dotenv not installed. Install with: pip install python-dotenv")
except Exception as e:
    print(f"Could not load .env file: {e}")


def extract_control_points_with_ai(text, api_key=None):
    """
    Use OpenAI API to extract control points from varying document formats
    """
    from openai import OpenAI
    
    # Get API key from environment or parameter
    if api_key is None:
        api_key = os.environ.get('OPENAI_API_KEY')
    
    if not api_key:
        print("No API key provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        print("Using fallback extraction instead...")
        return fallback_extraction(text)
    
    prompt = """You are analyzing a Swedish construction quality control document (egenkontroll). 

Your task is to extract ONLY the actual control points (kontrollpunkter/riktlinjer) from this document. 

IMPORTANT: A single control point may contain MULTIPLE related paragraphs or sentences that form one coherent requirement. Keep these together as ONE item. For example, if a control point describes material selection requirements across several paragraphs, they should be combined into a single control point entry.

Control points are substantive requirements, checks, or quality criteria that need to be verified during construction. They typically describe:
- Design requirements (projektering)
- Material specifications
- Environmental requirements
- Energy requirements
- Safety measures
- Technical specifications
- Ventilation requirements
- Waste management requirements

When extracting control points:
- Keep related paragraphs together as ONE control point (e.g., material selection requirements that span multiple paragraphs)
- Look for thematic groupings - if multiple paragraphs discuss the same topic or requirement area, combine them
- Each control point should represent a distinct requirement or check, even if it's described across multiple sentences/paragraphs

DO NOT extract:
- Document headers (Datum, Projekt, Byggherre, Checklista, Miljöplan, Fastighetskontoret)
- Column headers (Kontrollpunkt, Verifierat status, Kravkod, etc.)
- Page numbers or dates
- Status/verification fields
- Table formatting text
- Goal statements that just say "Mål:" followed by general goals
- Administrative text about who fills in what
- Code references like "SS BE 1", "X SS H/I 3" (unless part of the actual requirement text)
- Gibberish text like "g n n m ä t s v a"
- Generic phrases like "Byggherren är ansvarig för samtliga krav"
- Metadata about verification processes

Return ONLY a JSON array of strings, where each string is one complete control point requirement (which may include multiple related paragraphs). No preamble, no markdown formatting, just the JSON array.

Example of what TO extract as ONE item (even though it has multiple paragraphs):
- "Alla material, produkter och kemikalier som krävs i byggprocessen skall vara bästa miljö- och hälsoval. BASTA-systemet används för produktval. Material bedöms enligt Byggvarubedömningen (BVB). Material innehållande s.k. utfasningsämnen enligt Kemikalieinspektionens Priodatabas får inte finnas i material och kemikalier som används."

Document text:
"""
    
    try:
        print("Calling OpenAI API...")
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o",  # or "gpt-4-turbo" or "gpt-3.5-turbo"
            messages=[
                {"role": "user", "content": prompt + text}
            ],
            max_tokens=4000,
            temperature=0
        )
        
        print(f"API call successful")
        
        # Extract text from response
        result_text = response.choices[0].message.content
        
        if not result_text or not result_text.strip():
            print("Empty response from API")
            return fallback_extraction(text)
        
        print(f"Response preview: {result_text[:200]}")
        
        # Clean up the response (remove markdown code blocks if present)
        result_text = result_text.strip()
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        
        # Parse JSON
        control_points = json.loads(result_text)
        
        if not isinstance(control_points, list):
            print("API response is not a list")
            return fallback_extraction(text)
        
        # Clean up newlines and extra whitespace
        control_points = [
            ' '.join(cp.replace('\n', ' ').split()) 
            for cp in control_points
            if isinstance(cp, str) and cp.strip()
        ]
        
        return control_points
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Response text preview: {result_text[:500] if 'result_text' in locals() else 'N/A'}")
        return fallback_extraction(text)
    except Exception as e:
        print(f"Error using AI extraction: {e}")
        return fallback_extraction(text)


def fallback_extraction(text):
    """
    Improved fallback method if AI extraction fails
    """
    print("Using fallback extraction method...")
    
    # Remove common headers and noise
    text = re.sub(r'Datum:\s*\d+-\d+-\d+', '', text)
    text = re.sub(r'Projekt:.*?(?=\n)', '', text)
    text = re.sub(r'Byggherre:.*?(?=\n)', '', text)
    text = re.sub(r'Checklista/Miljöplan.*?(?=\n)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Fastighetskontoret.*?(?=\n)', '', text)
    text = re.sub(r'FN \d{4}-\d{2}-\d{2}.*?(?=\n)', '', text)
    text = re.sub(r'Egenkontroll[^\n]*', '', text)
    text = re.sub(r'Kontrollpunkt\s+Verifierat status', '', text)
    text = re.sub(r'VERIFIERAT RESULTAT', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Byggherren är ansvarig för samtliga krav', '', text)
    text = re.sub(r'= riktlinje som stäms av.*?(?=\n)', '', text)
    text = re.sub(r'\*\) Med egenkontroll avses.*?(?=\n)', '', text)
    
    # Remove section headers (all caps words)
    text = re.sub(r'\n[A-ZÅÄÖ\s]{10,}\n', '\n', text)
    
    # Remove gibberish patterns (reversed/mangled text like "g n n m ä")
    text = re.sub(r'(?:\b\w\s+){5,}', ' ', text)
    
    # Remove code references like "X SS BE 1"
    text = re.sub(r'X\s+SS\s+[A-Z/]+\s+\d+', '', text)
    text = re.sub(r'SS\s+[A-Z/]+\s+\d+', '', text)
    text = re.sub(r'BS\s+[A-Z/]+\s+\d+', '', text)
    
    # Remove "Mål:" lines
    text = re.sub(r'Mål:.*?(?=\n)', '', text)
    
    # Split into paragraphs
    text = re.sub(r'\n{3,}', '\n\n', text)
    chunks = [chunk.strip() for chunk in text.split('\n\n') if chunk.strip()]
    
    # Filter out noise
    noise_keywords = [
        'fyller i aktuellt datum',
        'granskningsdatum',
        'granskningskommentarer',
        'Typ av dokument',
        'Sida ',
        'Skede',
        'Kravkod',
        'Metod/Verktyg',
        'Berörd konsult',
        'FN 2009',
        'med förtydliganden',
        'Verifiering',
        'Projektering',
        'Produktion',
        'Förvaltning',
        'FK:s bedömning',
        'Dokumentation',
        'Baskrav',
        'BYGGARBETSPLATSEN',
        'TOMTMARK OCH GRÖNYTOR',
        'KVALITETSSÄKRING'
    ]
    
    filtered_chunks = []
    for chunk in chunks:
        # Skip if too short
        if len(chunk) < 50:
            continue
        
        # Skip if contains noise keywords
        if any(keyword.lower() in chunk.lower() for keyword in noise_keywords):
            continue
        
        # Skip if it's mostly uppercase (likely a header)
        alpha_chars = [c for c in chunk if c.isalpha()]
        if alpha_chars and sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars) > 0.6:
            continue
        
        # Must contain typical Swedish requirement words
        requirement_words = ['ska', 'skall', 'beaktas', 'utformas', 'väljs', 'planera', 'ordnas', 'finnas']
        if not any(word in chunk.lower() for word in requirement_words):
            continue
        
        filtered_chunks.append(chunk)
    
    return filtered_chunks


def process_egenkontroll_document(pdf_path):
    """
    Main function to process egenkontroll documents
    """
    # Extract text from PDF
    cache_file = pdf_path.replace('.pdf', '_text.pkl')
    
    if not os.path.exists(cache_file):
        print(f"Extracting text from {pdf_path}...")
        text = extract_text(pdf_path)
        with open(cache_file, "wb") as f:
            pickle.dump(text, f)
    else:
        print(f"Loading cached text...")
        with open(cache_file, "rb") as f:
            text = pickle.load(f)
    
    # Extract control points using AI
    print("Extracting control points...")
    control_points = extract_control_points_with_ai(text)
    
    # Additional cleanup for newlines (in case they weren't cleaned earlier)
    print("Cleaning up text...")
    control_points = [
        ' '.join(cp.replace('\n', ' ').split()) 
        for cp in control_points
    ]
    
    # Remove any remaining duplicates
    seen = set()
    unique_control_points = []
    for cp in control_points:
        if cp not in seen and len(cp) > 40:  # Keep only substantial points
            seen.add(cp)
            unique_control_points.append(cp)
    
    control_points = unique_control_points
    
    # Save results
    output_file = pdf_path.replace('.pdf', '_kontrollpunkter.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(control_points, f, ensure_ascii=False, indent=2)
    
    print(f"\nExtracted {len(control_points)} control points")
    print(f"Saved to: {output_file}")
    
    # Preview
    print("\n=== First 5 control points ===")
    for i, cp in enumerate(control_points[:5], 1):
        print(f"\n{i}. {cp[:200]}{'...' if len(cp) > 200 else ''}")
    
    return control_points


if __name__ == "__main__":
    # Process the example document
    control_points = process_egenkontroll_document('egenkontroll_base.pdf')
    
    # The control_points list can now be used for further processing
    print(f"\n✓ Successfully extracted {len(control_points)} control points")