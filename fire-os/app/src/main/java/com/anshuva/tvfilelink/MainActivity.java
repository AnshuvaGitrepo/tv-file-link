package com.anshuva.tvfilelink;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
import android.net.ConnectivityManager;
import android.net.LinkAddress;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.text.InputType;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.RelativeSizeSpan;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.File;
import java.io.IOException;
import java.net.Inet4Address;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int BACKGROUND = 0xff0e131e;
    private static final int PANEL = 0xff171f2e;
    private static final int ROW = 0xff243044;
    private static final int BORDER = 0xff303a4c;
    private static final int INK = 0xfff5f4f0;
    private static final int MUTED = 0xffaebacd;
    private static final int GOLD = 0xfff4d68c;
    private static final int FOCUS = 0xffffe7aa;
    private static final int LIVE = 0xffa7dfc2;
    private static final ExecutorService NETWORK = Executors.newSingleThreadExecutor();
    private static final ExecutorService WORKER = Executors.newSingleThreadExecutor();
    static { System.loadLibrary("tvfilelink"); }
    private static native byte[] nativeOperate(byte[] root, byte[] action, byte[] path, byte[] name);

    // Transfer (browser) state
    private String address;
    private Button transfer;
    private TextView transferStatus;
    private TextView transferDetails;
    private TextView transferAddress;
    private TextView codeLabel;
    private TextView code;
    private int sessionGeneration;
    private boolean foreground;

    // File manager state
    private File library;
    private List<Storage.Location> locations = new ArrayList<>();
    private Storage.Location current;
    private String folder = "";          // path inside current.root, "" = top
    private int sort = FileOps.SORT_NAME;
    private File clipboard;               // item waiting for Paste
    private boolean clipboardMove;
    private String lastListing = "";
    private boolean busy;
    private boolean accessHint;           // a "how to allow storage" hint is on screen
    private boolean readOnly;             // current location cannot be written (USB on Fire OS 6/7)

    private LinearLayout locationBar;
    private TextView folderLabel;
    private TextView spaceLabel;
    private TextView message;
    private LinearLayout rows;
    private Button up;
    private Button newFolder;
    private Button paste;
    private Button sortButton;
    private Button refresh;

    private final android.os.Handler ticker = new android.os.Handler(android.os.Looper.getMainLooper());
    // While a transfer is active, show browser uploads without pressing Refresh.
    // Skipped while a file row has focus so the remote focus never jumps.
    private final Runnable autoRefresh = new Runnable() {
        @Override public void run() {
            if (address == null || !foreground) return;
            try {
                String now = FileOps.signature(FileOps.list(currentDir(), sort));
                if (!now.equals(lastListing) && !rows.hasFocus() && !busy) refreshFiles(null);
            } catch (Exception ignored) {}
            ticker.postDelayed(this, 3000);
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        library = new File(getFilesDir(), "library");
        library.mkdirs();
        final LinearLayout screen = column();
        boolean compact = getResources().getConfiguration().screenHeightDp < 440;
        int inset = dp(compact ? 24 : 36);
        int verticalInset = dp(compact ? 14 : 24);
        screen.setPadding(inset, verticalInset, inset, verticalInset);
        screen.setBackgroundColor(BACKGROUND);
        setContentView(screen);
        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(0, 0, 0, dp(compact ? 8 : 14));
        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.as_logo);
        logo.setContentDescription("AS logo");
        logo.setBackground(shape(ROW, 12, 0xff645637));
        logo.setPadding(dp(1), dp(1), dp(1), dp(1));
        logo.setClipToOutline(true);
        int logoSize = dp(compact ? 47 : 56);
        LinearLayout.LayoutParams logoLayout = new LinearLayout.LayoutParams(logoSize, logoSize);
        logoLayout.rightMargin = dp(14);
        header.addView(logo, logoLayout);
        TextView title = label("TV File Link", compact ? 30 : 34, INK, true);
        title.setPadding(0, 0, 0, 0);
        header.addView(title);
        screen.addView(header);
        LinearLayout body = new LinearLayout(this);
        screen.addView(body, new LinearLayout.LayoutParams(-1, 0, 1));

        // ---- Wi-Fi Transfer rail (unchanged behaviour: browser sees My files only)
        ScrollView transferPanel = new ScrollView(this);
        transferPanel.setBackground(shape(PANEL, 16, BORDER));
        transferPanel.setVerticalScrollBarEnabled(false);
        transferPanel.setFocusable(false);
        transferPanel.setFillViewport(true);
        body.addView(transferPanel, new LinearLayout.LayoutParams(dp(compact ? 262 : 320), -1));
        LinearLayout rail = column();
        rail.setPadding(dp(18), dp(compact ? 9 : 14), dp(18), dp(compact ? 9 : 14));
        transferPanel.addView(rail);
        rail.addView(label("Wi-Fi Transfer", compact ? 22 : 25, INK, true));
        transferStatus = label("Transfer active", 14, LIVE, true);
        rail.addView(transferStatus);
        transferDetails = label("", 17, MUTED, false);
        rail.addView(transferDetails);
        // Address and code are sized to be read from the couch.
        transferAddress = label("", compact ? 17 : 15, INK, true);
        transferAddress.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        transferAddress.setTextColor(0xffffffff);
        if (Build.VERSION.SDK_INT >= 26) {
            transferAddress.setMaxLines(1);
            transferAddress.setAutoSizeTextTypeUniformWithConfiguration(12, compact ? 18 : 22, 1, TypedValue.COMPLEX_UNIT_SP);
        }
        rail.addView(transferAddress, new LinearLayout.LayoutParams(-1, -2));
        codeLabel = label("6-digit code", 16, MUTED, true);
        rail.addView(codeLabel);
        code = label("", compact ? 34 : 46, GOLD, true);
        code.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        code.setLetterSpacing(.18f);
        code.setBackground(shape(BACKGROUND, 9, BORDER));
        code.setGravity(Gravity.CENTER);
        code.setPadding(dp(8), dp(7), dp(8), dp(7));
        LinearLayout.LayoutParams codeLayout = new LinearLayout.LayoutParams(-1, -2);
        codeLayout.bottomMargin = dp(compact ? 5 : 10);
        rail.addView(code, codeLayout);
        transfer = button("Start transfer", this::toggleTransfer, true);
        rail.addView(transfer);

        // ---- File manager
        LinearLayout main = column();
        main.setBackground(shape(PANEL, 16, BORDER));
        main.setPadding(dp(16), dp(10), dp(16), dp(8));
        LinearLayout.LayoutParams mainParams = new LinearLayout.LayoutParams(0, -1, 1);
        mainParams.leftMargin = dp(16);
        body.addView(main, mainParams);
        HorizontalScrollView locationScroll = new HorizontalScrollView(this);
        locationScroll.setHorizontalScrollBarEnabled(false);
        locationScroll.setFocusable(false);
        locationBar = new LinearLayout(this);
        locationScroll.addView(locationBar);
        main.addView(locationScroll);
        LinearLayout titleLine = new LinearLayout(this);
        titleLine.setGravity(Gravity.BOTTOM);
        folderLabel = label("My files", 22, INK, true);
        folderLabel.setSingleLine(true);
        folderLabel.setEllipsize(android.text.TextUtils.TruncateAt.START);
        titleLine.addView(folderLabel, new LinearLayout.LayoutParams(0, -2, 1));
        spaceLabel = label("", 14, MUTED, false);
        titleLine.addView(spaceLabel);
        main.addView(titleLine);
        LinearLayout controls = new LinearLayout(this);
        main.addView(controls);
        up = button("Up", this::goUp);
        controls.addView(up);
        newFolder = button("New folder", () -> askName("New folder", "", null));
        controls.addView(newFolder);
        paste = button("Paste", this::paste);
        controls.addView(paste);
        sortButton = button("Sort: Name", this::cycleSort);
        controls.addView(sortButton);
        refresh = button("Refresh", () -> { refreshLocations(); refreshFiles(null); });
        controls.addView(refresh);
        ScrollView scroller = new ScrollView(this);
        scroller.setFocusable(false);
        main.addView(scroller, new LinearLayout.LayoutParams(-1, 0, 1));
        rows = column();
        scroller.addView(rows);
        message = label("", 16, FOCUS, false);
        message.setMaxLines(3);
        main.addView(message);

        paintTransfer();
        refreshLocations();
        current = locations.get(0);
        refreshFiles(null);
        transfer.requestFocus();
    }

    // USB drive / SD card plugged in or removed while the app is open: update the tabs at once.
    private final android.content.BroadcastReceiver mountReceiver = new android.content.BroadcastReceiver() {
        @Override public void onReceive(Context context, android.content.Intent intent) {
            if (current == null || busy) return;
            refreshLocations();
            refreshFiles(null);
        }
    };

    @Override protected void onStart() {
        super.onStart();
        foreground = true;
        android.content.IntentFilter filter = new android.content.IntentFilter();
        filter.addAction(android.content.Intent.ACTION_MEDIA_MOUNTED);
        filter.addAction(android.content.Intent.ACTION_MEDIA_UNMOUNTED);
        filter.addAction(android.content.Intent.ACTION_MEDIA_REMOVED);
        filter.addAction(android.content.Intent.ACTION_MEDIA_EJECT);
        filter.addAction(android.content.Intent.ACTION_MEDIA_BAD_REMOVAL);
        filter.addDataScheme("file");
        registerReceiver(mountReceiver, filter);
    }

    @Override protected void onResume() {
        super.onResume();
        // A USB drive may have been plugged in, or storage access granted in Settings.
        if (current != null) {
            clearAccessHint();
            refreshLocations();
            refreshFiles(null);
        }
    }

    @Override protected void onStop() {
        try { unregisterReceiver(mountReceiver); } catch (IllegalArgumentException ignored) {}
        foreground = false;
        closeTransfer();
        super.onStop();
    }

    @Override public void onBackPressed() {
        if (!folder.isEmpty()) goUp();
        else if (current != null && !current.library) switchLocation(locations.get(0));
        else super.onBackPressed();
    }

    @Override public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_MENU) {  // remote Menu key = Options for the focused item
            View focused = getCurrentFocus();
            if (focused != null && focused.getTag() instanceof File) {
                actions((File) focused.getTag());
                return true;
            }
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        if (requestCode == Storage.PERMISSION_REQUEST) {
            clearAccessHint();
            refreshLocations();
            refreshFiles(null);
        }
    }

    /** Replace the "how to allow storage" hint once access has been granted. */
    private void clearAccessHint() {
        if (accessHint && Storage.hasAccess(this)) {
            accessHint = false;
            say("Storage access is on.");
        }
    }

    // ------------------------------------------------------------------ small UI helpers
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private LinearLayout column() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    private TextView label(String text, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setPadding(0, dp(4), 0, dp(8));
        if (bold) view.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        return view;
    }

    private GradientDrawable shape(int color, int radius, int stroke) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color);
        shape.setCornerRadius(dp(radius));
        if (stroke != 0) shape.setStroke(dp(1), stroke);
        return shape;
    }

    private Button button(String text, Runnable action) {
        return button(text, action, false);
    }

    private Button button(String text, Runnable action, boolean primary) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setTextSize(16);
        button.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        button.setMinWidth(dp(44));
        button.setMinimumWidth(dp(44));
        button.setFocusable(true);
        button.setMinimumHeight(dp(39));
        button.setMinHeight(dp(39));
        button.setPadding(dp(12), dp(4), dp(12), dp(4));
        int[] disabled = {-android.R.attr.state_enabled};
        int[] focused = {android.R.attr.state_focused};
        int[] normal = {};
        button.setTextColor(new ColorStateList(new int[][]{disabled, focused, normal},
            new int[]{0xff8290a5, BACKGROUND, primary ? BACKGROUND : INK}));
        StateListDrawable background = new StateListDrawable();
        background.addState(disabled, shape(PANEL, 8, BORDER));
        background.addState(focused, shape(FOCUS, 8, GOLD));
        background.addState(normal, shape(primary ? GOLD : ROW, 8, 0));
        button.setBackground(background);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-2, -2);
        params.setMargins(0, dp(3), dp(9), dp(6));
        button.setLayoutParams(params);
        button.setOnClickListener(view -> action.run());
        return button;
    }

    private void say(String text) { message.setText(text == null ? "" : text); }

    // ------------------------------------------------------------------ native transfer server
    private static byte[] utf8(String text) { return text.getBytes(StandardCharsets.UTF_8); }

    private JSONObject call(String action, String path, String name) throws Exception {
        JSONObject result = new JSONObject(new String(
            nativeOperate(utf8(library.getAbsolutePath()), utf8(action), utf8(path), utf8(name)), StandardCharsets.UTF_8));
        if (result.has("error")) throw new Exception(result.getString("error"));
        return result;
    }

    private String localAddress() {
        ConnectivityManager manager = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        if (manager == null) return "";
        for (int transport : new int[]{NetworkCapabilities.TRANSPORT_WIFI, NetworkCapabilities.TRANSPORT_ETHERNET}) {
            for (Network network : manager.getAllNetworks()) {
                NetworkCapabilities capabilities = manager.getNetworkCapabilities(network);
                if (capabilities == null || !capabilities.hasTransport(transport)) continue;
                LinkProperties properties = manager.getLinkProperties(network);
                if (properties == null) continue;
                for (LinkAddress link : properties.getLinkAddresses()) {
                    if (link.getAddress() instanceof Inet4Address && !link.getAddress().isLoopbackAddress())
                        return link.getAddress().getHostAddress();
                }
            }
        }
        return "";
    }

    private void paintTransfer() {
        transfer.setText(address == null ? "Start transfer" : "Stop transfer");
        boolean active = address != null;
        int visibility = active ? View.VISIBLE : View.GONE;
        transferStatus.setVisibility(visibility);
        transferAddress.setVisibility(visibility);
        codeLabel.setVisibility(visibility);
        code.setVisibility(visibility);
        if (active) {
            String[] details = address.split(" ", 2);
            transferDetails.setText("On your phone or computer, open this address in a browser:");
            transferAddress.setText(details[0]);
            code.setText(details[1]);
        } else {
            transferDetails.setText("Send files from a phone or computer on the same Wi-Fi network. They arrive in My files.");
        }
    }

    private void toggleTransfer() {
        if (address != null) {
            closeTransfer();
            refreshFiles(null);
            return;
        }
        final int generation = ++sessionGeneration;
        transfer.setEnabled(false);
        transfer.setText("Starting…");
        say("");
        NETWORK.execute(() -> {
            try {
                String ip = localAddress();
                if (ip.isEmpty()) throw new Exception("Connect your Fire TV to Wi-Fi or Ethernet first.");
                String result = call("start", "", ip).getString("value");
                runOnUiThread(() -> {
                    if (!foreground || generation != sessionGeneration) return;
                    address = result;
                    transfer.setEnabled(true);
                    paintTransfer();
                    transfer.requestFocus();
                    ticker.removeCallbacks(autoRefresh);
                    ticker.postDelayed(autoRefresh, 3000);
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!foreground || generation != sessionGeneration) return;
                    transfer.setEnabled(true);
                    paintTransfer();
                    say(error.getMessage());
                    transfer.requestFocus();
                });
            }
        });
    }

    private void closeTransfer() {
        ticker.removeCallbacks(autoRefresh);
        sessionGeneration++;
        address = null;
        transfer.setEnabled(true);
        paintTransfer();
        NETWORK.execute(() -> {
            try { call("stop", "", ""); } catch (Exception ignored) {}
        });
    }

    // ------------------------------------------------------------------ locations
    private void refreshLocations() {
        String selected = current == null ? null : current.key();
        locations = Storage.locations(this, library);
        Storage.Location match = null;
        for (Storage.Location location : locations) if (location.key().equals(selected)) match = location;
        if (current != null && match == null) {           // e.g. USB drive removed
            say(current.label + " is no longer available.");
            folder = "";
            match = locations.get(0);
        }
        if (match != null) current = match;
        View focused = getCurrentFocus();
        boolean barFocused = focused != null && focused.getParent() == locationBar;
        String focusedKey = barFocused && focused.getTag() instanceof String ? (String) focused.getTag() : null;
        locationBar.removeAllViews();
        for (Storage.Location location : locations) {
            boolean selectedTab = current != null && location.key().equals(current.key());
            Button tab = button(location.label, () -> switchLocation(location), selectedTab);
            tab.setTag(location.key());
            tab.setCompoundDrawablesWithIntrinsicBounds(location.library ? R.drawable.filelink_folder : R.drawable.filelink_storage, 0, 0, 0);
            tab.setCompoundDrawablePadding(dp(8));
            tab.setCompoundDrawableTintList(new ColorStateList(
                new int[][]{new int[]{android.R.attr.state_focused}, new int[]{}},
                new int[]{BACKGROUND, selectedTab ? BACKGROUND : GOLD}));
            tab.setContentDescription("Location " + location.label);
            locationBar.addView(tab);
            if (location.key().equals(focusedKey)) tab.requestFocus();
        }
    }

    private void switchLocation(Storage.Location location) {
        current = location;
        folder = "";
        say("");
        refreshLocations();
        refreshFiles(null);
    }

    private File currentDir() {
        return folder.isEmpty() ? current.root : new File(current.root, folder);
    }

    private void goUp() {
        if (folder.isEmpty()) return;
        String child = folder.contains("/") ? folder.substring(folder.lastIndexOf('/') + 1) : folder;
        int slash = folder.lastIndexOf('/');
        folder = slash < 0 ? "" : folder.substring(0, slash);
        refreshFiles(child);
    }

    private void cycleSort() {
        sort = (sort + 1) % FileOps.SORT_LABELS.length;
        sortButton.setText("Sort: " + FileOps.SORT_LABELS[sort]);
        refreshFiles(null);
        sortButton.requestFocus();
    }

    // ------------------------------------------------------------------ listing
    private void refreshFiles(String focusName) {
        boolean rowHadFocus = rows.hasFocus();
        rows.removeAllViews();
        folderLabel.setText(current.label + (folder.isEmpty() ? "" : " / " + folder));
        spaceLabel.setText(Storage.spaceLine(current.root));
        up.setEnabled(!folder.isEmpty());
        paste.setVisibility(clipboard == null ? View.GONE : View.VISIBLE);
        if (clipboard != null) paste.setText((clipboardMove ? "Move here: " : "Paste: ") + shorten(clipboard.getName(), 18));
        boolean locked = !current.library && !Storage.hasAccess(this);
        readOnly = !locked && current.removable && !Storage.canWrite(current.root);
        newFolder.setEnabled(!locked && !readOnly);
        sortButton.setEnabled(!locked);
        if (readOnly) paste.setVisibility(View.GONE);
        if (locked) {
            lastListing = "";
            TextView explain = label("TV File Link needs permission to show " + current.label
                + ". Your files stay on this TV; only you can browse them here.", 17, MUTED, false);
            rows.addView(explain);
            Button allow = button("Allow storage access", () -> { accessHint = true; say(Storage.request(this)); }, true);
            allow.setContentDescription("Allow storage access");
            rows.addView(allow);
            if (rowHadFocus) allow.requestFocus();
            return;
        }
        List<File> files;
        try {
            files = FileOps.list(currentDir(), sort);
        } catch (IOException error) {
            lastListing = "";
            say(error.getMessage());
            if (rowHadFocus) refresh.requestFocus();
            return;
        }
        lastListing = FileOps.signature(files);
        if (readOnly) {
            TextView note = label("Read-only on this Fire TV: apps can open and copy files from " + current.label
                + ", but cannot change it. Use Copy, then Paste in My files or Internal storage.", 15, GOLD, false);
            note.setContentDescription("Read-only drive");
            rows.addView(note);
        }
        if (files.isEmpty()) rows.addView(label(current.library && folder.isEmpty()
            ? "My files is empty. Start Wi-Fi Transfer to send files here, or copy files from another location."
            : "This folder is empty.", 17, MUTED, false));
        View focusTarget = null;
        for (File file : files) {
            View row = fileRow(file);
            rows.addView(row);
            if (focusName != null && focusName.equals(file.getName())) focusTarget = ((LinearLayout) row).getChildAt(0);
        }
        if (focusTarget != null) focusTarget.requestFocus();
        else if (rowHadFocus && !focusFirstRow()) refresh.requestFocus();
    }

    /** Focus the first file row (skipping notes such as the read-only message). */
    private boolean focusFirstRow() {
        for (int i = 0; i < rows.getChildCount(); i++) {
            View child = rows.getChildAt(i);
            if (child instanceof LinearLayout && child.requestFocus()) return true;
        }
        return false;
    }
    private static String shorten(String text, int max) {
        return text.length() <= max ? text : text.substring(0, max - 1) + "…";
    }

    private int iconFor(FileOps.Kind kind) {
        switch (kind) {
            case FOLDER: return R.drawable.filelink_folder;
            case IMAGE: return R.drawable.filelink_image;
            case VIDEO: return R.drawable.filelink_video;
            case AUDIO: return R.drawable.filelink_audio;
            default: return R.drawable.filelink_document;
        }
    }

    private View fileRow(File file) {
        FileOps.Kind kind = FileOps.kind(file);
        boolean directory = kind == FileOps.Kind.FOLDER;
        String details = directory ? "Folder" : FileOps.size(file.length());
        details += "  ·  " + FileOps.date(file.lastModified());
        SpannableString text = new SpannableString(file.getName() + "\n" + details);
        text.setSpan(new RelativeSizeSpan(0.74f), file.getName().length() + 1, text.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        Button row = button("", () -> {
            if (directory) {
                folder = folder.isEmpty() ? file.getName() : folder + "/" + file.getName();
                refreshFiles(null);
                focusFirstRow();
            } else {
                Viewers.open(this, file, sort);
            }
        });
        row.setText(text);
        row.setTag(file);
        row.setMaxLines(2);
        row.setContentDescription((directory ? "Folder " : "File ") + file.getName());
        row.setCompoundDrawablesWithIntrinsicBounds(iconFor(kind), 0, 0, 0);
        row.setCompoundDrawablePadding(dp(12));
        row.setCompoundDrawableTintList(new ColorStateList(
            new int[][]{new int[]{android.R.attr.state_focused}, new int[]{}},
            new int[]{BACKGROUND, directory ? GOLD : MUTED}));
        row.setEllipsize(android.text.TextUtils.TruncateAt.END);
        row.setGravity(Gravity.CENTER_VERTICAL | Gravity.LEFT);
        LinearLayout.LayoutParams rowLayout = new LinearLayout.LayoutParams(0, dp(54), 1);
        rowLayout.setMargins(0, dp(3), dp(9), dp(5));
        row.setLayoutParams(rowLayout);
        row.setOnLongClickListener(view -> { actions(file); return true; });
        LinearLayout item = new LinearLayout(this);
        item.addView(row);
        Button options = button("Options", () -> actions(file));
        options.setContentDescription("Options for " + file.getName());
        options.setTag(file);
        LinearLayout.LayoutParams optionsLayout = new LinearLayout.LayoutParams(-2, dp(54));
        optionsLayout.setMargins(0, dp(3), 0, dp(5));
        options.setLayoutParams(optionsLayout);
        item.addView(options);
        return item;
    }

    // ------------------------------------------------------------------ actions
    private void actions(File file) {
        boolean directory = file.isDirectory();
        List<String> items = new ArrayList<>();
        items.add("Open");
        if (!directory && FileOps.kind(file) != FileOps.Kind.OTHER) items.add("Open with another app");
        items.add("Copy");
        if (!readOnly) {            // a read-only drive (USB on Fire OS 6/7) cannot be changed
            items.add("Move");
            items.add("Rename");
            items.add("Delete");
        }
        items.add("Details");
        if (!current.library) items.add("Copy to My files");
        if (current.library && !directory) items.add("Download to a phone or computer");
        new AlertDialog.Builder(this).setTitle(file.getName()).setItems(items.toArray(new String[0]), (dialog, which) -> {
            switch (items.get(which)) {
                case "Open":
                    if (directory) {
                        folder = folder.isEmpty() ? file.getName() : folder + "/" + file.getName();
                        refreshFiles(null);
                    } else {
                        Viewers.open(this, file, sort);
                    }
                    break;
                case "Open with another app": Viewers.openWith(this, file); break;
                case "Copy": setClipboard(file, false); break;
                case "Move": setClipboard(file, true); break;
                case "Rename": askName("Rename", file.getName(), file); break;
                case "Delete": confirmDelete(file); break;
                case "Details": details(file); break;
                case "Copy to My files": runTransfer(file, library, false); break;
                case "Download to a phone or computer":
                    new AlertDialog.Builder(this).setTitle("Download this file")
                        .setMessage("Select Start transfer, open the address on your other device, enter the code, and select Download next to this file.")
                        .setPositiveButton("OK", null).show();
                    break;
                default: break;
            }
        }).show();
    }

    private void setClipboard(File file, boolean move) {
        clipboard = file;
        clipboardMove = move;
        say((move ? "Ready to move " : "Ready to copy ") + file.getName()
            + ". Open the destination (any location or folder) and select " + (move ? "Move here." : "Paste."));
        refreshFiles(file.getName());
    }

    private void paste() {
        if (clipboard == null) return;
        if (readOnly) {
            say(current.label + " is read-only on this Fire TV. Paste into My files or Internal storage.");
            return;
        }
        if (!clipboard.exists()) {
            say(clipboard.getName() + " no longer exists.");
            clipboard = null;
            refreshFiles(null);
            return;
        }
        runTransfer(clipboard, currentDir(), clipboardMove);
    }

    /** Copies or moves source into destination with a cancellable progress dialog. */
    private void runTransfer(File source, File destination, boolean move) {
        final boolean[] cancelled = {false};
        final long[] lastUpdate = {0};
        TextView progressText = label("Preparing…", 18, INK, false);
        progressText.setPadding(dp(24), dp(12), dp(24), dp(12));
        AlertDialog progressDialog = new AlertDialog.Builder(this)
            .setTitle((move ? "Moving " : "Copying ") + source.getName())
            .setView(progressText).setCancelable(false)
            .setNegativeButton("Cancel", (d, w) -> cancelled[0] = true).show();
        busy = true;
        WORKER.execute(() -> {
            String result;
            File created = null;
            try {
                FileOps.Progress progress = (done, total, name) -> {
                    if (cancelled[0]) return false;
                    long now = SystemClock.uptimeMillis();
                    if (now - lastUpdate[0] > 250) {
                        lastUpdate[0] = now;
                        int percent = total > 0 ? (int) (done * 100 / total) : 100;
                        String line = percent + "%   " + FileOps.size(done) + " of " + FileOps.size(total) + "\n" + name;
                        runOnUiThread(() -> progressText.setText(line));
                    }
                    return true;
                };
                created = move ? FileOps.move(source, destination, progress) : FileOps.copy(source, destination, progress);
                result = (move ? "Moved " : "Copied ") + source.getName()
                    + (created.getName().equals(source.getName()) ? "" : " as " + created.getName()) + ".";
            } catch (FileOps.CancelledException e) {
                result = "Cancelled. " + (move ? "The original is unchanged." : "No copy was kept.");
            } catch (IOException e) {
                result = e.getMessage();
            }
            String shown = result;
            File focus = created;
            runOnUiThread(() -> {
                busy = false;
                if (progressDialog.isShowing()) progressDialog.dismiss();
                if (move && focus != null) clipboard = null;
                say(shown);
                refreshFiles(focus != null && focus.getParentFile() != null
                    && focus.getParentFile().getAbsolutePath().equals(currentDir().getAbsolutePath()) ? focus.getName() : null);
            });
        });
    }

    private void confirmDelete(File file) {
        if (!file.isDirectory()) {
            new AlertDialog.Builder(this).setTitle("Delete " + file.getName() + "?")
                .setMessage("This cannot be undone.")
                .setNegativeButton("Cancel", null).setPositiveButton("Delete", (d, w) -> delete(file)).show();
            return;
        }
        WORKER.execute(() -> {
            int count = FileOps.countItems(file);
            runOnUiThread(() -> {
                String text = count == 0 ? "This folder is empty."
                    : "The folder and the " + count + (count == 1 ? " item" : " items") + " inside it will be deleted. This cannot be undone.";
                new AlertDialog.Builder(this).setTitle("Delete folder " + file.getName() + "?")
                    .setMessage(text).setNegativeButton("Cancel", null)
                    .setPositiveButton("Delete", (d, w) -> delete(file)).show();
            });
        });
    }

    private void delete(File file) {
        busy = true;
        WORKER.execute(() -> {
            String result;
            try {
                FileOps.deleteRecursive(file);
                result = "Deleted " + file.getName() + ".";
                if (file.equals(clipboard)) clipboard = null;
            } catch (IOException e) {
                result = e.getMessage();
            }
            String shown = result;
            runOnUiThread(() -> {
                busy = false;
                say(shown);
                refreshFiles(null);
                focusFirstRow();
            });
        });
    }

    private void details(File file) {
        boolean directory = file.isDirectory();
        String place = current.label + (folder.isEmpty() ? "" : " / " + folder);
        StringBuilder text = new StringBuilder();
        text.append("Type: ").append(directory ? "Folder" : FileOps.mime(file)).append('\n');
        text.append("Size: ").append(directory ? "calculating…" : FileOps.size(file.length()) + " (" + file.length() + " bytes)").append('\n');
        text.append("Modified: ").append(FileOps.date(file.lastModified())).append('\n');
        text.append("Location: ").append(place);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle(file.getName())
            .setMessage(text.toString()).setPositiveButton("OK", null).show();
        if (directory) {
            WORKER.execute(() -> {
                long size = FileOps.totalSize(file);
                int count = FileOps.countItems(file);
                String done = text.toString().replace("calculating…", FileOps.size(size) + " in " + count + (count == 1 ? " item" : " items"));
                runOnUiThread(() -> { if (dialog.isShowing()) dialog.setMessage(done); });
            });
        }
    }

    /** New folder (target == null) or rename (target = item). */
    private void askName(String title, String initial, File target) {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_TEXT);
        input.setText(initial);
        input.selectAll();
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle(title).setView(input)
            .setNegativeButton("Cancel", null).setPositiveButton("Save", null).create();
        input.requestFocus();
        dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            String name = input.getText().toString().trim();
            try {
                if (target == null) FileOps.mkdir(currentDir(), name);
                else {
                    FileOps.rename(target, name);
                    if (target.equals(clipboard)) clipboard = new File(target.getParentFile(), name);
                }
                ((InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE))
                    .hideSoftInputFromWindow(input.getWindowToken(), 0);
                dialog.dismiss();
                say("");
                refreshFiles(name);
            } catch (IOException error) {
                input.setError(error.getMessage());
            }
        }));
        dialog.show();
    }
}
