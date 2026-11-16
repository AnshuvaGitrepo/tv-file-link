package com.anshuva.tvfilelink;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.VideoView;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Full-screen viewers shown as dialogs, so the app (and an active transfer) stays in the foreground. */
final class Viewers {
    private static final ExecutorService DECODER = Executors.newSingleThreadExecutor();
    private static final int TEXT_LIMIT = 512 * 1024;

    private Viewers() {}

    static void open(Activity activity, File file, int sort) {
        switch (FileOps.kind(file)) {
            case IMAGE: image(activity, FileOps.siblingsOfKind(file, FileOps.Kind.IMAGE, sort), file); break;
            case VIDEO: case AUDIO: media(activity, file); break;
            case TEXT: text(activity, file); break;
            default: openWith(activity, file); break;
        }
    }

    private static Dialog fullScreen(Activity activity, View content) {
        Dialog dialog = new Dialog(activity, android.R.style.Theme_Black_NoTitleBar_Fullscreen);
        dialog.setContentView(content);
        return dialog;
    }

    private static TextView caption(Activity activity, FrameLayout frame) {
        TextView caption = new TextView(activity);
        caption.setTextColor(0xfff5f4f0);
        caption.setTextSize(18);
        caption.setPadding(dp(activity, 20), dp(activity, 10), dp(activity, 20), dp(activity, 10));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xcc0e131e);
        bg.setCornerRadius(dp(activity, 10));
        caption.setBackground(bg);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        params.bottomMargin = dp(activity, 28);
        frame.addView(caption, params);
        return caption;
    }

    private static int dp(Activity activity, int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }

    // ---------------------------------------------------------------- images
    private static void image(Activity activity, List<File> images, File start) {
        FrameLayout frame = new FrameLayout(activity);
        frame.setBackgroundColor(Color.BLACK);
        ImageView view = new ImageView(activity);
        view.setScaleType(ImageView.ScaleType.FIT_CENTER);
        view.setContentDescription("Image viewer");
        frame.addView(view, new FrameLayout.LayoutParams(-1, -1));
        TextView caption = caption(activity, frame);
        Dialog dialog = fullScreen(activity, frame);
        int[] index = {Math.max(0, images.indexOf(start))};
        Runnable show = new Runnable() {
            @Override public void run() {
                File file = images.get(index[0]);
                caption.setText(file.getName() + "   (" + (index[0] + 1) + " of " + images.size() + ")"
                    + (images.size() > 1 ? "   Left / Right: previous / next" : "") + "   Back: close");
                view.setImageDrawable(null);
                int width = activity.getResources().getDisplayMetrics().widthPixels;
                int height = activity.getResources().getDisplayMetrics().heightPixels;
                DECODER.execute(() -> {
                    Bitmap bitmap = decode(file, width, height);
                    activity.runOnUiThread(() -> {
                        if (!dialog.isShowing()) return;
                        if (bitmap != null) view.setImageBitmap(bitmap);
                        else caption.setText(file.getName() + ": this image cannot be shown.   Back: close");
                    });
                });
            }
        };
        dialog.setOnKeyListener((d, keyCode, event) -> {
            if (event.getAction() != KeyEvent.ACTION_DOWN || images.size() < 2) return false;
            if (keyCode == KeyEvent.KEYCODE_DPAD_RIGHT || keyCode == KeyEvent.KEYCODE_MEDIA_FAST_FORWARD) {
                index[0] = (index[0] + 1) % images.size(); show.run(); return true;
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT || keyCode == KeyEvent.KEYCODE_MEDIA_REWIND) {
                index[0] = (index[0] - 1 + images.size()) % images.size(); show.run(); return true;
            }
            return false;
        });
        dialog.show();
        show.run();
    }

    /** Decodes an image scaled down to about the screen size (keeps memory low on the Stick). */
    static Bitmap decode(File file, int width, int height) {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(file.getAbsolutePath(), bounds);
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null;
        int sample = 1;
        while (bounds.outWidth / (sample * 2) >= width || bounds.outHeight / (sample * 2) >= height) sample *= 2;
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = sample;
        try {
            return BitmapFactory.decodeFile(file.getAbsolutePath(), options);
        } catch (OutOfMemoryError e) {
            return null;
        }
    }

    // ---------------------------------------------------------------- video and audio
    private static String clock(int millis) {
        int s = Math.max(0, millis / 1000);
        return s >= 3600 ? String.format(Locale.US, "%d:%02d:%02d", s / 3600, s / 60 % 60, s % 60)
            : String.format(Locale.US, "%d:%02d", s / 60, s % 60);
    }

    private static void media(Activity activity, File file) {
        boolean audio = FileOps.kind(file) == FileOps.Kind.AUDIO;
        FrameLayout frame = new FrameLayout(activity);
        frame.setBackgroundColor(Color.BLACK);
        VideoView video = new VideoView(activity);
        video.setContentDescription(audio ? "Audio player" : "Video player");
        frame.addView(video, new FrameLayout.LayoutParams(-1, -1, Gravity.CENTER));
        if (audio) {
            TextView title = new TextView(activity);
            title.setText("♫  " + file.getName());
            title.setTextColor(0xfff4d68c);
            title.setTextSize(30);
            title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
            frame.addView(title, new FrameLayout.LayoutParams(-2, -2, Gravity.CENTER));
        }
        TextView caption = caption(activity, frame);
        caption.setText(file.getName() + "   Loading...");
        Dialog dialog = fullScreen(activity, frame);
        Handler handler = new Handler(Looper.getMainLooper());
        boolean[] ready = {false};
        boolean[] finished = {false};
        Runnable status = new Runnable() {
            @Override public void run() {
                if (!dialog.isShowing()) return;
                if (ready[0] && !finished[0]) {
                    int length = video.getDuration();
                    caption.setText((video.isPlaying() ? "Playing  " : "Paused  ") + file.getName() + "   "
                        + clock(video.getCurrentPosition()) + (length > 0 ? " / " + clock(length) : "")
                        + "   Select: play/pause   Left/Right: -10 s / +10 s   Back: close");
                }
                handler.postDelayed(this, 500);
            }
        };
        video.setOnPreparedListener(player -> {
            ready[0] = true;
            video.start();
        });
        video.setOnCompletionListener(player -> {
            finished[0] = true;
            caption.setText("Finished  " + file.getName() + "   Select: play again   Back: close");
        });
        video.setOnErrorListener((player, what, extra) -> {
            ready[0] = false;
            caption.setText(file.getName() + ": this format cannot be played here. Back, then Options > Open with another app.");
            return true;
        });
        dialog.setOnKeyListener((d, keyCode, event) -> {
            if (event.getAction() != KeyEvent.ACTION_DOWN || !ready[0]) return false;
            switch (keyCode) {
                case KeyEvent.KEYCODE_DPAD_CENTER: case KeyEvent.KEYCODE_ENTER:
                case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE: case KeyEvent.KEYCODE_SPACE:
                    finished[0] = false;
                    if (video.isPlaying()) video.pause(); else video.start();
                    return true;
                case KeyEvent.KEYCODE_MEDIA_PLAY: video.start(); return true;
                case KeyEvent.KEYCODE_MEDIA_PAUSE: video.pause(); return true;
                case KeyEvent.KEYCODE_DPAD_RIGHT: case KeyEvent.KEYCODE_MEDIA_FAST_FORWARD:
                    video.seekTo(Math.min(video.getDuration(), video.getCurrentPosition() + 10000)); return true;
                case KeyEvent.KEYCODE_DPAD_LEFT: case KeyEvent.KEYCODE_MEDIA_REWIND:
                    video.seekTo(Math.max(0, video.getCurrentPosition() - 10000)); return true;
                default: return false;
            }
        });
        dialog.setOnDismissListener(d -> {
            handler.removeCallbacksAndMessages(null);
            video.stopPlayback();
        });
        dialog.show();
        video.setVideoPath(file.getAbsolutePath());
        handler.post(status);
    }

    // ---------------------------------------------------------------- text
    private static void text(Activity activity, File file) {
        FrameLayout frame = new FrameLayout(activity);
        frame.setBackgroundColor(0xff0e131e);
        ScrollView scroller = new ScrollView(activity);
        scroller.setFocusable(true);
        scroller.setFocusableInTouchMode(true);
        TextView body = new TextView(activity);
        body.setTypeface(Typeface.MONOSPACE);
        body.setTextColor(0xfff5f4f0);
        body.setTextSize(18);
        int pad = dp(activity, 40);
        body.setPadding(pad, pad, pad, dp(activity, 110));
        body.setText("Loading...");
        scroller.addView(body, new ViewGroup.LayoutParams(-1, -2));
        frame.addView(scroller, new FrameLayout.LayoutParams(-1, -1));
        TextView caption = caption(activity, frame);
        caption.setText(file.getName() + "   Up/Down: scroll   Back: close");
        Dialog dialog = fullScreen(activity, frame);
        dialog.setOnKeyListener((d, keyCode, event) -> {
            if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
            if (keyCode == KeyEvent.KEYCODE_DPAD_DOWN) { scroller.smoothScrollBy(0, dp(activity, 220)); return true; }
            if (keyCode == KeyEvent.KEYCODE_DPAD_UP) { scroller.smoothScrollBy(0, -dp(activity, 220)); return true; }
            return false;
        });
        dialog.show();
        DECODER.execute(() -> {
            String content;
            try (InputStream in = new FileInputStream(file)) {
                byte[] data = new byte[(int) Math.min(file.length(), TEXT_LIMIT)];
                int read = 0, n;
                while (read < data.length && (n = in.read(data, read, data.length - read)) > 0) read += n;
                content = new String(data, 0, read, StandardCharsets.UTF_8);
                if (file.length() > TEXT_LIMIT) content += "\n\n[Showing the first 512 KB of " + FileOps.size(file.length()) + "]";
                if (content.isEmpty()) content = "(This file is empty.)";
            } catch (IOException e) {
                content = "This file cannot be read: " + e.getMessage();
            }
            String shown = content;
            activity.runOnUiThread(() -> body.setText(shown));
        });
    }

    // ---------------------------------------------------------------- other apps
    static void openWith(Activity activity, File file) {
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(LocalFileProvider.uriFor(file), FileOps.mime(file));
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            // Android TV ships placeholder "stub" handlers that accept every media type and close at once
            // without showing anything. Ignore them so the user gets a clear message instead of nothing.
            java.util.List<android.content.ComponentName> stubs = new java.util.ArrayList<>();
            int real = 0;
            for (android.content.pm.ResolveInfo info : activity.getPackageManager().queryIntentActivities(intent, 0)) {
                String pkg = info.activityInfo.packageName;
                if (pkg.equals(activity.getPackageName())) continue;
                if (pkg.contains("frameworkpackagestubs")) stubs.add(new android.content.ComponentName(pkg, info.activityInfo.name));
                else real++;
            }
            if (real == 0) throw new ActivityNotFoundException();
            Intent chooser = Intent.createChooser(intent, "Open " + file.getName() + " with");
            if (!stubs.isEmpty()) chooser.putExtra(Intent.EXTRA_EXCLUDE_COMPONENTS, stubs.toArray(new android.os.Parcelable[0]));
            activity.startActivity(chooser);
        } catch (ActivityNotFoundException e) {
            new AlertDialog.Builder(activity).setTitle("No app can open this file")
                .setMessage("No app on this TV can open " + file.getName() + ". Install an app for this file type, "
                    + "or start Wi-Fi Transfer and download the file to another device (copy it to My files first).")
                .setPositiveButton("OK", null).show();
        }
    }
}
