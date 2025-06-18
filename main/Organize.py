import sys
import os
import shutil

sys.path.insert(0, "D:\Softwears\Anaconda\envs\Py310\python.exe")

def group_files(files):
    groups = []
    if not files:
        return groups

    files_sorted = sorted(files)
    current_group = []
    current_prefix = None

    for file in files_sorted:
        name = os.path.splitext(file)[0]  # 去除扩展名
        if not current_group:
            current_group.append(file)
            current_prefix = name
        else:
            if name.startswith(current_prefix):
                current_group.append(file)
            else:
                new_prefix = os.path.commonprefix([current_prefix, name])
                if new_prefix:
                    current_prefix = new_prefix
                    current_group.append(file)
                else:
                    groups.append((current_prefix, current_group))
                    current_group = [file]
                    current_prefix = name

    if current_group:
        groups.append((current_prefix, current_group))
    return groups

def main():
    current_dir = os.getcwd()
    mp4_files = [f for f in os.listdir(current_dir) if f.lower().endswith('.mp4')]
    
    groups = group_files(mp4_files)

    for prefix, files in groups:
        # 去除前缀末尾的空白字符作为文件夹名
        folder_name = prefix.rstrip()
        folder_path = os.path.join(current_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        for file in files:
            src = os.path.join(current_dir, file)
            dst = os.path.join(folder_path, file)
            shutil.move(src, dst)
            print(f"Moved '{file}' to '{folder_name}/'")

if __name__ == "__main__":
    main()