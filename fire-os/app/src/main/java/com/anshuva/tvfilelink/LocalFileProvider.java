package com.anshuva.tvfilelink;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;

/**
 * Read-only provider used for "Open with another app". It is not exported; other apps can only
 * open a file when TV File Link hands them a one-time read grant for that exact URI.
 */
public final class LocalFileProvider extends ContentProvider {
    static final String AUTHORITY = "com.anshuva.tvfilelink.files";

    static Uri uriFor(File file) {
        return new Uri.Builder().scheme("content").authority(AUTHORITY)
            .appendPath("f").appendQueryParameter("p", file.getAbsolutePath()).build();
    }

    private File fileFor(Uri uri) throws FileNotFoundException {
        String path = uri.getQueryParameter("p");
        if (path == null) throw new FileNotFoundException("No file.");
        try {
            File file = new File(path).getCanonicalFile();
            if (!file.isFile()) throw new FileNotFoundException("Not a file.");
            Context context = getContext();
            String library = new File(context.getFilesDir(), "library").getCanonicalPath();
            boolean inLibrary = file.getPath().startsWith(library + File.separator);
            boolean inShared = file.getPath().startsWith("/storage/") || file.getPath().startsWith("/sdcard/")
                || file.getPath().startsWith("/mnt/");
            if (!inLibrary && !inShared) throw new FileNotFoundException("Not allowed.");
            return file;
        } catch (IOException e) {
            throw new FileNotFoundException(e.getMessage());
        }
    }

    @Override public boolean onCreate() { return true; }

    @Override public String getType(Uri uri) {
        try { return FileOps.mime(fileFor(uri)); } catch (FileNotFoundException e) { return null; }
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!"r".equals(mode)) throw new FileNotFoundException("Read-only.");
        return ParcelFileDescriptor.open(fileFor(uri), ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
        File file;
        try { file = fileFor(uri); } catch (FileNotFoundException e) { return null; }
        String[] columns = projection != null ? projection : new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE};
        MatrixCursor cursor = new MatrixCursor(columns, 1);
        Object[] row = new Object[columns.length];
        for (int i = 0; i < columns.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(columns[i])) row[i] = file.getName();
            else if (OpenableColumns.SIZE.equals(columns[i])) row[i] = file.length();
        }
        cursor.addRow(row);
        return cursor;
    }

    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri, String selection, String[] args) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { throw new UnsupportedOperationException(); }
}
