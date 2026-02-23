import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.nlp_pipeline import TextCleaner, BadWordsClassifier, classify_text

def test_text_cleaner():
    print("Testing TextCleaner...")
    
    # Arabic tests
    ar_text = "أهلاً بك، هَذِهِ تَجْرِبَةٌ!"
    cleaned_ar = TextCleaner.clean(ar_text)
    print(f"Original: {ar_text} -> Cleaned: {cleaned_ar}")
    assert "اهلا" in cleaned_ar
    assert "تجربه" in cleaned_ar # Te Marbuta -> he
    
    # English tests
    en_text = "Hello World! This is a Test."
    cleaned_en = TextCleaner.clean(en_text)
    print(f"Original: {en_text} -> Cleaned: {cleaned_en}")
    assert cleaned_en == "hello world this is a test"

def test_classifier():
    print("\nTesting BadWordsClassifier...")
    
    # Good Arabic text
    good_ar = "انا ابحث عن ابني المفقود"
    label_good_ar = classify_text(good_ar)
    print(f"Text: '{good_ar}' -> Label: {label_good_ar}")
    assert label_good_ar == "good"
    
    # Bad Arabic text
    bad_ar = "انت حمار جدا"
    label_bad_ar = classify_text(bad_ar)
    print(f"Text: '{bad_ar}' -> Label: {label_bad_ar}")
    assert label_bad_ar == "bad"
    
    # Mixed bad text
    mixed_bad = "Stop being such an idiot وواطي"
    label_mixed = classify_text(mixed_bad)
    print(f"Text: '{mixed_bad}' -> Label: {label_mixed}")
    assert label_mixed == "bad"

if __name__ == "__main__":
    try:
        test_text_cleaner()
        test_classifier()
        print("\nAll verification tests passed!")
    except AssertionError as e:
        print(f"\nVerification failed: {e}")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
