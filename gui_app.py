import concurrent.futures
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from image_processor import add_overlay_from_file

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


if TkinterDnD is not None:
    class DnDCTk(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
else:
    DnDCTk = ctk.CTk


class App(DnDCTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Image Overlay App")
        self.geometry("900x640")
        self.minsize(760, 520)

        self.overlay_image = None
        self.overlay_filepath = ""
        self.file_labels = []
        self.processing_queue = None
        self.processing_total = 0
        self.processing_completed = 0
        self.processing_failures = []
        self.processing_output_dir = ""
        self.is_processing = False
        self.dnd_enabled = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.file_list_frame = ctk.CTkFrame(self)
        self.file_list_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.action_frame = ctk.CTkFrame(self)
        self.action_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")

        self.setup_settings_widgets()
        self.setup_file_list_widgets()
        self.setup_action_widgets()
        self.initialize_drag_and_drop()
        self.update_compatibility_notice()

    def setup_settings_widgets(self):
        self.settings_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.overlay_button = ctk.CTkButton(
            self.settings_frame,
            text="Select Overlay Image",
            command=self.select_overlay,
        )
        self.overlay_button.grid(row=0, column=0, padx=10, pady=10)

        self.overlay_label = ctk.CTkLabel(
            self.settings_frame,
            text="No overlay selected",
            wraplength=180,
        )
        self.overlay_label.grid(row=0, column=1, padx=10, pady=10)

        ctk.CTkLabel(self.settings_frame, text="Position:").grid(
            row=0,
            column=2,
            padx=(20, 5),
            pady=10,
            sticky="e",
        )
        self.position_var = ctk.StringVar(value="bottom-right")
        self.position_menu = ctk.CTkOptionMenu(
            self.settings_frame,
            values=["bottom-right", "bottom-left", "top-right", "top-left", "center"],
            variable=self.position_var,
        )
        self.position_menu.grid(row=0, column=3, padx=(0, 10), pady=10, sticky="w")

        ctk.CTkLabel(self.settings_frame, text="Scale:").grid(
            row=1,
            column=0,
            padx=10,
            pady=10,
            sticky="e",
        )
        self.scale_value_var = ctk.StringVar(value="25%")
        self.scale_slider = ctk.CTkSlider(
            self.settings_frame,
            from_=0.05,
            to=1.0,
            command=self.on_scale_change,
        )
        self.scale_slider.set(0.25)
        self.scale_slider.grid(row=1, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        self.scale_label = ctk.CTkLabel(self.settings_frame, textvariable=self.scale_value_var)
        self.scale_label.grid(row=1, column=3, padx=10, pady=10, sticky="w")

        ctk.CTkLabel(self.settings_frame, text="Padding:").grid(
            row=2,
            column=0,
            padx=10,
            pady=10,
            sticky="e",
        )
        self.padding_value_var = ctk.StringVar(value="2%")
        self.padding_slider = ctk.CTkSlider(
            self.settings_frame,
            from_=0.0,
            to=0.2,
            command=self.on_padding_change,
        )
        self.padding_slider.set(0.02)
        self.padding_slider.grid(row=2, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        self.padding_label = ctk.CTkLabel(self.settings_frame, textvariable=self.padding_value_var)
        self.padding_label.grid(row=2, column=3, padx=10, pady=10, sticky="w")

        self.compatibility_label = ctk.CTkLabel(
            self.settings_frame,
            text="",
            justify="left",
            wraplength=760,
            text_color=("gray40", "gray70"),
        )
        self.compatibility_label.grid(row=3, column=0, columnspan=4, padx=10, pady=(0, 10), sticky="w")

    def setup_file_list_widgets(self):
        self.file_list_frame.grid_rowconfigure(0, weight=1)
        self.file_list_frame.grid_columnconfigure(0, weight=1)
        self.scrollable_list = ctk.CTkScrollableFrame(self.file_list_frame, label_text="Images to Process")
        self.scrollable_list.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.drop_message_var = ctk.StringVar()
        self.drop_label = ctk.CTkLabel(
            self.scrollable_list,
            textvariable=self.drop_message_var,
            font=("", 20),
            justify="center",
        )
        self.drop_label.pack(expand=True, padx=20, pady=50)
        self.refresh_drop_message()

    def setup_action_widgets(self):
        self.action_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.select_files_button = ctk.CTkButton(
            self.action_frame,
            text="Select Images",
            command=self.select_files,
        )
        self.select_files_button.grid(row=0, column=0, padx=10, pady=10)

        self.clear_button = ctk.CTkButton(
            self.action_frame,
            text="Clear List",
            command=self.clear_list,
        )
        self.clear_button.grid(row=0, column=1, padx=10, pady=10)

        self.process_button = ctk.CTkButton(
            self.action_frame,
            text="Apply Overlays",
            command=self.start_processing,
            fg_color="green",
            hover_color="dark green",
        )
        self.process_button.grid(row=0, column=2, padx=10, pady=10)

        self.progress_bar = ctk.CTkProgressBar(self.action_frame)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="ew")

        self.status_label = ctk.CTkLabel(self.action_frame, text="Ready")
        self.status_label.grid(row=2, column=0, columnspan=3, padx=10, pady=(0, 10))

    def on_scale_change(self, value):
        self.scale_value_var.set(f"{int(value * 100)}%")

    def on_padding_change(self, value):
        self.padding_value_var.set(f"{int(value * 100)}%")

    def refresh_drop_message(self):
        if self.dnd_enabled:
            text = "Drag & Drop Images Here\nor\nClick 'Select Images' below"
        else:
            text = "Drag & drop unavailable on this Python/Tk build.\nUse 'Select Images' below."
        self.drop_message_var.set(text)

    def update_compatibility_notice(self):
        notes = []
        if tk.TkVersion < 8.6:
            notes.append(
                f"This Python build uses Tk {tk.TkVersion:.1f}. "
                "macOS compatibility is more reliable with a Tk 8.6+ build."
            )
        if not self.dnd_enabled:
            notes.append("Drag and drop is disabled. File selection still works.")
        self.compatibility_label.configure(text=" ".join(notes))

    def initialize_drag_and_drop(self):
        if TkinterDnD is None:
            self.dnd_enabled = False
            self.refresh_drop_message()
            return

        try:
            self.TkdndVersion = TkinterDnD._require(self)
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self.handle_drop)
            self.dnd_enabled = True
        except Exception:
            self.dnd_enabled = False

        self.refresh_drop_message()

    def _add_files_to_list(self, filepaths):
        accepted_files, skipped_files = self._filter_image_paths(filepaths)
        if not accepted_files and skipped_files:
            messagebox.showwarning("Unsupported Files", "Only image files can be added to the batch.")
            return

        self.drop_label.pack_forget()
        current_files = {label.cget("text") for label in self.file_labels}
        for filepath in accepted_files:
            if filepath not in current_files:
                label = ctk.CTkLabel(self.scrollable_list, text=filepath, anchor="w", justify="left")
                label.pack(anchor="w", padx=5, fill="x")
                self.file_labels.append(label)
                current_files.add(filepath)

        if skipped_files:
            messagebox.showwarning(
                "Skipped Files",
                f"Skipped {len(skipped_files)} unsupported item(s). Supported types: "
                + ", ".join(sorted(SUPPORTED_IMAGE_EXTENSIONS)),
            )

    def _filter_image_paths(self, filepaths):
        accepted_files = []
        skipped_files = []
        for filepath in filepaths:
            normalized = filepath.strip()
            extension = os.path.splitext(normalized)[1].lower()
            if os.path.isfile(normalized) and extension in SUPPORTED_IMAGE_EXTENSIONS:
                accepted_files.append(normalized)
            else:
                skipped_files.append(normalized)
        return accepted_files, skipped_files

    def select_overlay(self):
        filepath = filedialog.askopenfilename(
            title="Select an Overlay Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp")],
        )
        if filepath:
            try:
                with Image.open(filepath) as overlay_source:
                    self.overlay_image = overlay_source.convert("RGBA")
                self.overlay_filepath = filepath
                self.overlay_label.configure(text=os.path.basename(filepath))
            except Exception as error:
                messagebox.showerror("Error", f"Could not open overlay image:\n{error}")

    def select_files(self):
        filepaths = filedialog.askopenfilenames(
            title="Select Base Images",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp")],
        )
        if filepaths:
            self._add_files_to_list(filepaths)

    def handle_drop(self, event):
        filepaths = self.tk.splitlist(event.data)
        if filepaths:
            self._add_files_to_list(filepaths)

    def clear_list(self):
        if self.is_processing:
            return

        for label in self.file_labels:
            label.destroy()
        self.file_labels.clear()
        self.drop_label.pack(expand=True, padx=20, pady=50)
        self.status_label.configure(text="Ready")
        self.progress_bar.set(0)

    def start_processing(self):
        if self.is_processing:
            return

        if not self.overlay_filepath:
            messagebox.showerror("Error", "Please select an overlay image first.")
            return

        image_paths = [label.cget("text") for label in self.file_labels]
        if not image_paths:
            messagebox.showerror("Error", "Please add some images to process.")
            return

        output_dir = filedialog.askdirectory(title="Select a Folder to Save the Output")
        if not output_dir:
            return

        jobs = self._build_output_jobs(image_paths, output_dir)
        if not jobs:
            messagebox.showerror("Error", "No valid images were available to process.")
            return

        position = self.position_var.get()
        scale = self.scale_slider.get()
        padding = self.padding_slider.get()

        self.processing_queue = queue.Queue()
        self.processing_total = len(jobs)
        self.processing_completed = 0
        self.processing_failures = []
        self.processing_output_dir = output_dir
        self.progress_bar.set(0)
        self.status_label.configure(text=f"Processing 0/{self.processing_total} images...")
        self.set_processing_state(True)

        worker = threading.Thread(
            target=self._run_batch_processing,
            args=(jobs, position, scale, padding),
            daemon=True,
        )
        worker.start()
        self.after(100, self.poll_processing_queue)

    def _build_output_jobs(self, image_paths, output_dir):
        jobs = []
        reserved_paths = set()
        for image_path in image_paths:
            filename, _ext = os.path.splitext(os.path.basename(image_path))
            candidate = os.path.join(output_dir, f"{filename}_with_overlay.png")
            suffix = 1
            while candidate in reserved_paths or os.path.exists(candidate):
                candidate = os.path.join(output_dir, f"{filename}_with_overlay_{suffix}.png")
                suffix += 1
            reserved_paths.add(candidate)
            jobs.append((image_path, candidate))
        return jobs

    def _run_batch_processing(self, jobs, position, scale, padding):
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
                progress = self.processing_completed / self.processing_total
                self.progress_bar.set(progress)

                source_name = os.path.basename(message["source_path"])
                if message["success"]:
                    status_prefix = "Processed"
                else:
                    status_prefix = "Failed"
                    self.processing_failures.append((message["source_path"], message["error_message"]))

                self.status_label.configure(
                    text=f"{status_prefix} {self.processing_completed}/{self.processing_total}: {source_name}"
                )
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
        self.progress_bar.set(1 if self.processing_total else 0)

        failure_count = len(self.processing_failures)
        success_count = max(0, self.processing_total - failure_count)

        if failure_count == 0:
            self.status_label.configure(
                text=f"Done. Saved {success_count} image(s) to {self.processing_output_dir}"
            )
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

            self.status_label.configure(
                text=f"Completed with issues. {success_count} succeeded, {failure_count} failed."
            )
            messagebox.showwarning(
                "Completed With Issues",
                f"Processed {success_count} image(s) successfully.\n"
                f"Failed: {failure_count}\n\n"
                + "\n".join(preview_lines),
            )

        self.processing_queue = None

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        state = "disabled" if is_processing else "normal"
        self.overlay_button.configure(state=state)
        self.position_menu.configure(state=state)
        self.scale_slider.configure(state=state)
        self.padding_slider.configure(state=state)
        self.select_files_button.configure(state=state)
        self.clear_button.configure(state=state)
        self.process_button.configure(state=state)
