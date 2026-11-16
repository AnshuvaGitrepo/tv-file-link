package com.anshuva.tvfilelink;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.text.DateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** File manager operations on plain paths (app library, internal storage, USB drives). */
final class FileOps {
    static final int SORT_NAME = 0, SORT_DATE = 1, SORT_SIZE = 2;
    static final String[] SORT_LABELS = {"Name", "Date", "Size"};
    private static final String TEMP_PREFIX = ".tvlink-";  // transfer server staging files

    enum Kind { FOLDER, IMAGE, VIDEO, AUDIO, TEXT, OTHER }

    /** Reports copy progress; return false to cancel. */
    interface Progress { boolean update(long done, long total, String current); }

    static final class CancelledException extends IOException {
        CancelledException() { super("Cancelled."); }
    }

    private FileOps() {}

    static String extension(String name) {
        int dot = name.lastIndexOf('.');
        return dot <= 0 ? "" : name.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    static Kind kind(File file) {
        if (file.isDirectory()) return Kind.FOLDER;
        switch (extension(file.getName())) {
            case "jpg": case "jpeg": case "png": case "gif": case "webp": case "bmp": case "heic": case "heif":
                return Kind.IMAGE;
            case "mp4": case "m4v": case "mkv": case "webm": case "3gp": case "mov": case "ts": case "avi":
                return Kind.VIDEO;
            case "mp3": case "m4a": case "aac": case "wav": case "ogg": case "oga": case "flac": case "opus": case "mid":
                return Kind.AUDIO;
            case "txt": case "log": case "md": case "csv": case "json": case "xml": case "ini": case "conf":
            case "srt": case "vtt": case "html": case "htm": case "sh": case "properties": case "m3u":
                return Kind.TEXT;
            default:
                return Kind.OTHER;
        }
    }

    static String mime(File file) {
        String ext = extension(file.getName());
        String type = android.webkit.MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
        if (type != null) return type;
        switch (kind(file)) {
            case IMAGE: return "image/*";
            case VIDEO: return "video/*";
            case AUDIO: return "audio/*";
            case TEXT: return "text/plain";
            default: return "application/octet-stream";
        }
    }

    /** True when the entry is a symbolic link (or otherwise resolves elsewhere). */
    static boolean isLink(File file) {
        try {
            File parent = file.getParentFile();
            File canonicalParent = parent == null ? null : parent.getCanonicalFile();
            File expected = canonicalParent == null ? file : new File(canonicalParent, file.getName());
            return !expected.getCanonicalFile().equals(expected.getAbsoluteFile());
        } catch (IOException e) {
            return true;
        }
    }

    /** Folder contents: hidden and staging files and links left out, folders first. */
    static List<File> list(File dir, int sort) throws IOException {
        if (!dir.isDirectory()) throw new IOException("This folder is not available. It may have been removed.");
        File[] children = dir.listFiles();
        if (children == null) throw new IOException("This folder cannot be read. Check the storage permission.");
        List<File> result = new ArrayList<>();
        for (File child : children) {
            String name = child.getName();
            if (name.startsWith(".") || isLink(child)) continue;
            if (child.isDirectory() || child.isFile()) result.add(child);
        }
        Collections.sort(result, (a, b) -> {
            if (a.isDirectory() != b.isDirectory()) return a.isDirectory() ? -1 : 1;
            int byName = a.getName().compareToIgnoreCase(b.getName());
            if (sort == SORT_DATE) {
                int c = Long.compare(b.lastModified(), a.lastModified());
                return c != 0 ? c : byName;
            }
            if (sort == SORT_SIZE && a.isFile()) {
                int c = Long.compare(b.length(), a.length());
                return c != 0 ? c : byName;
            }
            return byName;
        });
        return result;
    }

    /** Fingerprint of a folder listing, used to notice changes made by the browser. */
    static String signature(List<File> files) {
        StringBuilder out = new StringBuilder();
        for (File f : files) out.append(f.getName()).append('|').append(f.length()).append('|').append(f.lastModified()).append('\n');
        return out.toString();
    }

    /** Returns an error message, or null when the name is acceptable. */
    static String checkName(String name) {
        if (name.isEmpty()) return "Enter a name.";
        if (name.equals(".") || name.equals("..")) return "Choose another name.";
        if (name.length() > 255) return "This name is too long.";
        if (name.startsWith(TEMP_PREFIX)) return "Names cannot start with " + TEMP_PREFIX;
        for (int i = 0; i < name.length(); i++) {
            char ch = name.charAt(i);
            if (ch < 32 || ch == 127 || ch == '/' || ch == '\\') return "Names cannot contain / or \\.";
        }
        return null;
    }

    static void mkdir(File parent, String name) throws IOException {
        String problem = checkName(name);
        if (problem != null) throw new IOException(problem);
        File target = new File(parent, name);
        if (target.exists()) throw new IOException("This name is already in use.");
        if (!target.mkdir()) throw new IOException("Could not create the folder. Check free space and the storage permission.");
    }

    static void rename(File item, String name) throws IOException {
        String problem = checkName(name);
        if (problem != null) throw new IOException(problem);
        if (name.equals(item.getName())) return;
        File target = new File(item.getParentFile(), name);
        if (target.exists() && !target.getName().equalsIgnoreCase(item.getName()))
            throw new IOException("This name is already in use.");
        if (!item.renameTo(target)) throw new IOException("Could not rename. The storage may be read-only.");
    }

    /** Number of files and folders inside a folder (not counting the folder itself). */
    static int countItems(File dir) {
        File[] children = dir.listFiles();
        if (children == null) return 0;
        int count = 0;
        for (File child : children) {
            count++;
            if (child.isDirectory() && !isLink(child)) count += countItems(child);
        }
        return count;
    }

    static long totalSize(File file) {
        if (!file.isDirectory()) return file.length();
        File[] children = file.listFiles();
        if (children == null) return 0;
        long total = 0;
        for (File child : children) if (!isLink(child)) total += totalSize(child);
        return total;
    }

    static void deleteRecursive(File file) throws IOException {
        if (file.isDirectory() && !isLink(file)) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) deleteRecursive(child);
        }
        if (!file.delete() && file.exists())
            throw new IOException("Could not delete " + file.getName() + ". The storage may be read-only.");
    }

    /** "name.ext", or "name (1).ext", "name (2).ext" ... when taken. */
    static File uniqueTarget(File dir, String name) {
        File target = new File(dir, name);
        if (!target.exists()) return target;
        int dot = name.lastIndexOf('.');
        boolean hasExt = dot > 0 && !new File(dir, name).isDirectory();
        String base = hasExt ? name.substring(0, dot) : name;
        String ext = hasExt ? name.substring(dot) : "";
        for (int i = 1; ; i++) {
            target = new File(dir, base + " (" + i + ")" + ext);
            if (!target.exists()) return target;
        }
    }

    private static void checkNotInside(File source, File destinationDir) throws IOException {
        String src = source.getCanonicalPath();
        String dst = destinationDir.getCanonicalPath();
        if (dst.equals(src) || dst.startsWith(src + File.separator))
            throw new IOException("A folder cannot be copied or moved into itself.");
    }

    /** Copies a file or folder into destinationDir; returns the new item. */
    static File copy(File source, File destinationDir, Progress progress) throws IOException {
        if (source.isDirectory()) checkNotInside(source, destinationDir);
        long[] done = {0};
        long total = totalSize(source);
        long free = destinationDir.getUsableSpace();
        if (free > 0 && total > free)
            throw new IOException("Not enough free space: " + size(total) + " needed, " + size(free) + " free.");
        File target = uniqueTarget(destinationDir, source.getName());
        try {
            copyInto(source, target, done, total, progress);
        } catch (IOException e) {
            if (target.exists()) {
                try { deleteRecursive(target); } catch (IOException ignored) {}
            }
            throw e;
        }
        return target;
    }

    private static void copyInto(File source, File target, long[] done, long total, Progress progress) throws IOException {
        if (source.isDirectory()) {
            if (!target.mkdir()) throw new IOException("Could not create " + target.getName() + ". Check free space.");
            File[] children = source.listFiles();
            if (children == null) return;
            for (File child : children) {
                if (isLink(child)) continue;
                copyInto(child, new File(target, child.getName()), done, total, progress);
            }
            return;
        }
        byte[] buffer = new byte[256 * 1024];
        try (InputStream in = new FileInputStream(source); OutputStream out = new FileOutputStream(target)) {
            int count;
            while ((count = in.read(buffer)) > 0) {
                out.write(buffer, 0, count);
                done[0] += count;
                if (progress != null && !progress.update(done[0], total, source.getName())) throw new CancelledException();
            }
            out.flush();
        }
        target.setLastModified(source.lastModified());
    }

    /** Moves a file or folder into destinationDir (rename when possible, else copy + delete). */
    static File move(File source, File destinationDir, Progress progress) throws IOException {
        if (source.getParentFile() != null && source.getParentFile().getCanonicalFile().equals(destinationDir.getCanonicalFile()))
            throw new IOException("The item is already in this folder.");
        if (source.isDirectory()) checkNotInside(source, destinationDir);
        File target = uniqueTarget(destinationDir, source.getName());
        if (source.renameTo(target)) return target;  // same drive: instant
        File copied = copy(source, destinationDir, progress);
        deleteRecursive(source);
        return copied;
    }

    static String size(long bytes) {
        if (bytes < 1024) return bytes + " B";
        String[] units = {"KB", "MB", "GB", "TB"};
        double value = bytes;
        int unit = -1;
        do { value /= 1024; unit++; } while (value >= 1024 && unit < units.length - 1);
        return String.format(Locale.US, value < 10 ? "%.1f %s" : "%.0f %s", value, units[unit]);
    }

    static String date(long millis) {
        return DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(new Date(millis));
    }

    static List<File> siblingsOfKind(File file, Kind kind, int sort) {
        try {
            List<File> out = new ArrayList<>();
            for (File f : list(file.getParentFile(), sort)) if (kind(f) == kind) out.add(f);
            return out;
        } catch (IOException e) {
            return new ArrayList<>(Arrays.asList(file));
        }
    }
}
