import os
import sys
import urllib.request
import shutil

MODEL_URL = "https://huggingface.co/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf"
MODEL_FILENAME = "Qwen2.5-14B-Instruct-Q4_K_M.gguf"

def download_with_progress(url, dest_path):
    print(f"Lade Modell herunter von:\n{url}\nZielpfad: {dest_path}\n")
    
    # Simple chunk-based download with progress bar using only standard library (works out-of-the-box everywhere)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        total_size = int(response.info().get('Content-Length', 0))
        chunk_size = 1024 * 1024 # 1MB chunks
        downloaded = 0
        
        with open(dest_path, "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    percent = downloaded * 100 / total_size
                    bar = "#" * int(percent / 5) + "-" * (20 - int(percent / 5))
                    sys.stdout.write(f"\r[{bar}] {percent:.1f}% ({downloaded / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB)")
                    sys.stdout.flush()
            sys.stdout.write("\n")
            print("✓ Download abgeschlossen!")

def setup_env(model_abs_path):
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    env_path = os.path.join(project_root, ".env")
    env_example = os.path.join(project_root, ".env.example")
    
    # Check if .env already exists
    if not os.path.exists(env_path):
        if os.path.exists(env_example):
            print("Erstelle neue .env aus .env.example...")
            shutil.copy2(env_example, env_path)
        else:
            print("Erstelle eine leere .env...")
            with open(env_path, "w") as f:
                f.write("# PaperVault Environment Config\n")
                
    # Update MODEL_PATH in .env
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    updated_lines = []
    found_model_path = False
    for line in lines:
        if line.strip().startswith("MODEL_PATH="):
            updated_lines.append(f"MODEL_PATH={model_abs_path}\n")
            found_model_path = True
        else:
            updated_lines.append(line)
            
    if not found_model_path:
        updated_lines.append(f"MODEL_PATH={model_abs_path}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)
        
    print(f"✓ .env erfolgreich aktualisiert! MODEL_PATH zeigt nun auf:\n{model_abs_path}")

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    models_dir = os.path.join(project_root, "models")
    os.makedirs(models_dir, exist_ok=True)
    
    dest_path = os.path.join(models_dir, MODEL_FILENAME)
    
    if os.path.exists(dest_path):
        print(f"Das Modell existiert bereits unter: {dest_path}")
        overwrite = input("Möchtest du es erneut herunterladen? (y/N): ").strip().lower()
        if overwrite != "y":
            setup_env(os.path.abspath(dest_path))
            return
            
    try:
        download_with_progress(MODEL_URL, dest_path)
        setup_env(os.path.abspath(dest_path))
        print("\n=== Setup erfolgreich! ===")
        print("Du kannst die App nun mit start_all.bat starten.")
    except Exception as e:
        print(f"\n❌ Fehler während des Setups: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
