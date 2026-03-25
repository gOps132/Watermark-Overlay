import concurrent.futures
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image

from image_processor import add_overlay_from_file


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


class ClassicApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Image Overlay App")
        self.geometry("900x640")
        self.minsize(760, 520)

        self.overlay_filepath = ""
        self.filepaths = []
        self.processing_queue = None
        self.processing_total = 0
        self.processing_completed = 0
        self.processing_failures = []
        self.processing_output_dir = ""
        self.is_processing = False

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.position_var = tk.StringVar(value="bottom-right")
        self.scale_var = tk.DoubleVar(value=0.25)
        self.padding_var = tk.DoubleVar(value=0.02)
        self.scale_text_var = tk.StringVar(value="25%")
        self.padding_text_var = tk.StringVar(value="2%")
        self.overlay_text_var = tk.StringVar(value="No overlay selected")
        self.status_var = tk.StringVar(value="Ready")

        self.setup_styles()
        self.setup_settings_widgets()
        self.setup_file_list_widgets()
        self.setup_action_widgets()

    def setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

    def setup_settings_widgets(self):
        frame = ttk.Frame(self, padding=12)
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        overlay_button = ttk.Button(frame, text="Select Overlay Image", command=self.select_overlay)
        overlay_button.grid(
            row=0,
            column=0,
            padx=(0, 10),
            pady=(0, 8),
            sticky="w",
        )
        self.overlay_button = overlay_button
        ttk.Label(frame, textvariable=self.overlay_text_var).grid(
            row=0,
            column=1,
            padx=(0, 20),
            pady=(0, 8),
            sticky="w",
        )

        ttk.Label(frame, text="Position").grid(row=0, column=2, padx=(0, 8), pady=(0, 8), sticky="e")
        position_menu = ttk.OptionMenu(
            frame,
            self.position_var,
            self.position_var.get(),
            "bottom-right",
            "bottom-left",
            "top-right",
            "top-left",
            "center",
        )
        position_menu.grid(row=0, column=3, pady=(0, 8), sticky="ew")
        self.position_menu = position_menu

        ttk.Label(frame, text="Scale").grid(row=1, column=0, padx=(0, 10), pady=8, sticky="e")
        scale_slider = ttk.Scale(
            frame,
            from_=0.05,
            to=1.0,
            variable=self.scale_var,
            command=self.on_scale_change,
        )
        scale_slider.grid(row=1, column=1, columnspan=2, padx=(0, 10), pady=8, sticky="ew")
        self.scale_slider = scale_slider
        ttk.Label(frame, textvariable=self.scale_text_var, width=6).grid(row=1, column=3, pady=8, sticky="w")

        ttk.Label(frame, text="Padding").grid(row=2, column=0, padx=(0, 10), pady=8, sticky="e")
        padding_slider = ttk.Scale(
            frame,
            from_=0.0,
            to=0.2,
            variable=self.padding_var,
            command=self.on_padding_change,
        )
        padding_slider.grid(row=2, column=1, columnspan=2, padx=(0, 10), pady=8, sticky="ew")
        self.padding_slider = padding_slider
        ttk.Label(frame, textvariable=self.padding_text_var, width=6).grid(row=2, column=3, pady=8, sticky="w")

        ttk.Label(
            frame,
            text=(
                f"Compatibility mode enabled. This Python build uses Tk {tk.TkVersion:.1f}, "
                "so the app is using the standard tkinter interface instead of CustomTkinter."
            ),
            wraplength=820,
            justify="left",
        ).grid(row=3, column=0, columnspan=4, pady=(8, 0), sticky="w")

    def setup_file_list_widgets(self):
        frame = ttk.LabelFrame(self, text="Images to Process", padding=12)
        frame.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="Drag and drop is disabled in compatibility mode.\nUse 'Select Images' below.",
            justify="center",
        ).grid(row=0, column=0, pady=(0, 12), sticky="ew")

        list_frame = ttk.Frame(frame)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.file_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
        self.file_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_listbox.configure(yscrollcommand=scrollbar.set)

    def setup_action_widgets(self):
        frame = ttk.Frame(self, padding=(12, 0, 12, 12))
        frame.grid(row=2, column=0, sticky="ew")
        frame.columnconfigure((0, 1, 2), weight=1)

        self.select_files_button = ttk.Button(frame, text="Select Images", command=self.select_files)
        self.select_files_button.grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="ew")

        self.clear_button = ttk.Button(frame, text="Clear List", command=self.clear_list)
        self.clear_button.grid(row=0, column=1, padx=8, pady=(0, 8), sticky="ew")

        self.process_button = ttk.Button(frame, text="Apply Overlays", command=self.start_processing)
        self.process_button.grid(row=0, column=2, padx=(8, 0), pady=(0, 8), sticky="ew")

        self.progress_bar = ttk.Progressbar(frame, mode="determinate", maximum=1.0)
        self.progress_bar.grid(row=1, column=0, columnspan=3, sticky="ew")

        ttk.Label(frame, textvariable=self.status_var).grid(row=2, column=0, columnspan=3, pady=(8, 0), sticky="w")

    def on_scale_change(self, _value):
        self.scale_text_var.set(f"{int(self.scale_var.get() * 100)}%")

    def on_padding_change(self, _value):
        self.padding_text_var.set(f"{int(self.padding_var.get() * 100)}%")

    def select_overlay(self):
        filepath = filedialog.askopenfilename(
            title="Select an Overlay Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp")],
        )
        if not filepath:
            return

        try:
            with Image.open(filepath) as overlay_source:
                overlay_source.verify()
            self.overlay_filepath = filepath
            self.overlay_text_var.set(os.path.basename(filepath))
        except Exception as error:
            messagebox.showerror("Error", f"Could not open overlay image:\n{error}")

    def select_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Select Base Images",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp")],
        )
        if filepaths:
            self.add_files(filepaths)

    def add_files(self, filepaths):
        accepted_files = []
        skipped_files = []
        existing = set(self.filepaths)

        for filepath in filepaths:
            extension = os.path.splitext(filepath)[1].lower()
            if os.path.isfile(filepath) and extension in SUPPORTED_IMAGE_EXTENSIONS:
                if filepath not in existing:
                    accepted_files.append(filepath)
                    existing.add(filepath)
            else:
                skipped_files.append(filepath)

        for filepath in accepted_files:
            self.filepaths.append(filepath)
            self.file_listbox.insert(tk.END, filepath)

        if skipped_files:
            messagebox.showwarning(
                "Skipped Files",
                f"Skipped {len(skipped_files)} unsupported item(s). Supported types: "
                + ", ".join(sorted(SUPPORTED_IMAGE_EXTENSIONS)),
            )

    def clear_list(self):
        if self.is_processing:
            return
        self.filepaths.clear()
        self.file_listbox.delete(0, tk.END)
        self.status_var.set("Ready")
        self.progress_bar["value"] = 0

    def start_processing(self):
        if self.is_processing:
            return
        if not self.overlay_filepath:
            messagebox.showerror("Error", "Please select an overlay image first.")
            return
        if not self.filepaths:
            messagebox.showerror("Error", "Please add some images to process.")
            return

        output_dir = filedialog.askdirectory(title="Select a Folder to Save the Output")
        if not output_dir:
            return

        jobs = self.build_output_jobs(output_dir)
        if not jobs:
            messagebox.showerror("Error", "No valid images were available to process.")
            return

        self.processing_queue = queue.Queue()
        self.processing_total = len(jobs)
        self.processing_completed = 0
        self.processing_failures = []
        self.processing_output_dir = output_dir
        self.progress_bar["value"] = 0
        self.status_var.set(f"Processing 0/{self.processing_total} images...")
        self.set_processing_state(True)

        worker = threading.Thread(
            target=self.run_batch_processing,
            args=(jobs, self.position_var.get(), self.scale_var.get(), self.padding_var.get()),
            daemon=True,
        )
        worker.start()
        self.after(100, self.poll_processing_queue)

    def build_output_jobs(self, output_dir):
        jobs = []
        reserved_paths = set()
        for image_path in self.filepaths:
            filename, _ext = os.path.splitext(os.path.basename(image_path))
            candidate = os.path.join(output_dir, f"{filename}_with_overlay.png")
            suffix = 1
            while candidate in reserved_paths or os.path.exists(candidate):
                candidate = os.path.join(output_dir, f"{filename}_with_overlay_{suffix}.png")
                suffix += 1
            reserved_paths.add(candidate)
            jobs.append((image_path, candidate))
        return jobs

    def run_batch_processing(self, jobs, position, scale, padding):
        max_workers = min(len(jobs), max(1, os.cpu_count() or 1), 4)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_job = {
                    executor.submit(
                        add_overlay_from_file,
                        source_path,
                        self.overlay_filepath,
                        output_path,
                        position,
                        scale,
                        padding,
                    ): (source_path, output_path)
                    for source_path, output_path in jobs
                }
                for future in concurrent.futures.as_completed(future_to_job):
                    source_path, output_path = future_to_job[future]
                    try:
                        success, error_message = future.result()
                    except Exception as error:
                        success = False
                        error_message = str(error)
                    self.processing_queue.put(
                        {
                            "type": "result",
                            "source_path": source_path,
                            "output_path": output_path,
                            "success": success,
                            "error_message": error_message,
                        }
                    )
        except Exception as error:
            self.processing_queue.put({"type": "fatal", "error_message": str(error)})
        finally:
            self.processing_queue.put({"type": "complete"})

    def poll_processing_queue(self):
        completed = False
        while self.processing_queue is not None:
            try:
                message = self.processing_queue.get_nowait()
            except queue.Empty:
                break

            message_type = message["type"]
            if message_type == "result":
                self.processing_completed += 1
                self.progress_bar["value"] = self.processing_completed / self.processing_total
                source_name = os.path.basename(message["source_path"])
                if message["success"]:
                    prefix = "Processed"
                else:
                    prefix = "Failed"
                    self.processing_failures.append((message["source_path"], message["error_message"]))
                self.status_var.set(f"{prefix} {self.processing_completed}/{self.processing_total}: {source_name}")
            elif message_type == "fatal":
                self.processing_failures.append(("Batch processor", message["error_message"]))
            elif message_type == "complete":
                completed = True

        if completed:
            self.finish_processing()
            return
        self.after(100, self.poll_processing_queue)

    def finish_processing(self):
        self.set_processing_state(False)
        self.progress_bar["value"] = 1 if self.processing_total else 0

        failure_count = len(self.processing_failures)
        success_count = max(0, self.processing_total - failure_count)

        if failure_count == 0:
            self.status_var.set(f"Done. Saved {success_count} image(s) to {self.processing_output_dir}")
            messagebox.showinfo(
                "Success",
                f"Processed {success_count} image(s).\nSaved to:\n{self.processing_output_dir}",
            )
        else:
            preview_lines = []
            for source_path, error_message in self.processing_failures[:5]:
                preview_lines.append(f"{os.path.basename(source_path)}: {error_message}")
            if failure_count > 5:
                preview_lines.append(f"...and {failure_count - 5} more failure(s).")

            self.status_var.set(f"Completed with issues. {success_count} succeeded, {failure_count} failed.")
            messagebox.showwarning(
                "Completed With Issues",
                f"Processed {success_count} image(s) successfully.\n"
                f"Failed: {failure_count}\n\n"
                + "\n".join(preview_lines),
            )

        self.processing_queue = None

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        state = tk.DISABLED if is_processing else tk.NORMAL
        self.overlay_button.configure(state=state)
        self.select_files_button.configure(state=state)
        self.clear_button.configure(state=state)
        self.process_button.configure(state=state)
        self.position_menu.configure(state=state)
        self.scale_slider.configure(state=state)
        self.padding_slider.configure(state=state)
