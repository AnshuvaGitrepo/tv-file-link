package com.anshuva.tvfilelink;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.storage.StorageManager;
import android.os.storage.StorageVolume;
import android.provider.Settings;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/** Storage locations the file manager can show, and the permission needed to reach them. */
final class Storage {
    static final int PERMISSION_REQUEST = 41;

    static final class Location {
        final String label;
        final File root;
        final boolean library;
        final boolean removable;

        Location(String label, File root, boolean library, boolean removable) {
            this.label = label;
            this.root = root;
            this.library = library;
            this.removable = removable;
        }

        String key() { return root.getAbsolutePath(); }
    }

    private Storage() {}

    /** My files (app library), internal shared storage, then each mounted USB drive or SD card. */
    static List<Location> locations(Context context, File library) {
        List<Location> list = new ArrayList<>();
        list.add(new Location("My files", library, true, false));
        File primary = Environment.getExternalStorageDirectory();
        if (primary != null && Environment.MEDIA_MOUNTED.equals(Environment.getExternalStorageState()))
            list.add(new Location("Internal storage", primary, false, false));
        File[] appDirs = context.getExternalFilesDirs(null);  // one entry per mounted volume
        StorageManager manager = (StorageManager) context.getSystemService(Context.STORAGE_SERVICE);
        int drive = 0;
        for (int i = 1; appDirs != null && i < appDirs.length; i++) {
            if (appDirs[i] == null) continue;
            String path = appDirs[i].getAbsolutePath();
            int cut = path.indexOf("/Android/data/");
            if (cut <= 0) continue;
            File root = new File(path.substring(0, cut));
            drive++;
            String label = "USB drive" + (drive > 1 ? " " + drive : "");
            if (manager != null) {
                StorageVolume volume = manager.getStorageVolume(root);
                if (volume != null && volume.getDescription(context) != null)
                    label = volume.getDescription(context);
            }
            list.add(new Location(label, root, false, true));
        }
        return list;
    }

    /** True when the app may read and write shared storage and USB drives. */
    static boolean hasAccess(Context context) {
        if (Build.VERSION.SDK_INT >= 30) return Environment.isExternalStorageManager();
        return context.checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED
            && context.checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED;
    }

    /**
     * Asks for access. Fire OS 6/7 (Android 7-9): the normal Storage permission prompt.
     * Fire OS 8 (Android 10/11): "All files" access in Settings. Some TV builds lack the direct
     * screen, so fall back to the general screen, then to the app's own settings page.
     * Returns a hint to show the user.
     */
    static String request(Activity activity) {
        if (Build.VERSION.SDK_INT < 30) {
            activity.requestPermissions(new String[]{
                Manifest.permission.READ_EXTERNAL_STORAGE, Manifest.permission.WRITE_EXTERNAL_STORAGE}, PERMISSION_REQUEST);
            return "Select Allow to let TV File Link show your storage.";
        }
        Uri app = Uri.parse("package:" + activity.getPackageName());
        Intent[] attempts = {
            new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION, app),
            new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION),
            new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, app),
        };
        String[] hints = {
            "Turn on \"Allow access to manage all files\", then press Back.",
            "Find TV File Link, turn on all files access, then press Back.",
            "Open Permissions > Storage, choose \"All files\" (or Allow), then press Back.",
        };
        for (int i = 0; i < attempts.length; i++) {
            try {
                activity.startActivity(attempts[i]);
                return hints[i];
            } catch (ActivityNotFoundException | SecurityException ignored) {
            }
        }
        return "Open Settings > Applications > Manage Installed Applications > TV File Link > Permissions and allow Storage (All files).";
    }

    /**
     * True when files can be created in dir. On Fire OS 6/7 (Android 7-9) apps may read USB drives and
     * SD cards but not write to them, so the file manager shows those drives read-only.
     */
    static boolean canWrite(File dir) {
        try {
            File probe = File.createTempFile(".tvlink-probe", null, dir);  // hidden: names starting with "." are not listed
            if (!probe.delete()) probe.deleteOnExit();
            return true;
        } catch (IOException | SecurityException e) {
            return false;
        }
    }

    static String spaceLine(File root) {
        long total = root.getTotalSpace();
        if (total <= 0) return "";
        return FileOps.size(root.getUsableSpace()) + " free of " + FileOps.size(total);
    }
}
