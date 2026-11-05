package com.doxoade.benzaiten;

import android.app.Activity;
import android.content.pm.PackageManager;
import android.media.AudioManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import rikka.shizuku.Shizuku;

public class MainActivity extends Activity {
    private WebView webView;
    private AudioManager audioManager;
    private static final String TAG = "SysUtilsMobile";
    private static final int SHIZUKU_CODE = 1001;

    private Handler monitorHandler;
    private Runnable monitorRunnable;
    private boolean isMonitoring = false;
    private long monitorIntervalMs = 2000;
    private String lastStateJson = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);

        webView.addJavascriptInterface(new HermesBridge(), "__dx_native__");
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.loadUrl("file:///android_asset/index.html");
        setContentView(webView);

        audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);
        monitorHandler = new Handler(Looper.getMainLooper());

        // No onCreate, junto com os outros listeners
        Shizuku.addRequestPermissionResultListener((requestCode, grantResult) -> {
            if (requestCode == SHIZUKU_CODE) {
                if (grantResult == PackageManager.PERMISSION_GRANTED) {
                    emitShizukuStatus("granted");
                } else {
                    emitShizukuStatus("denied");
                }
            }
        });

        // Escuta quando o Shizuku liga ou desliga
        Shizuku.addBinderReceivedListenerSticky(() -> {
            runOnUiThread(this::checkShizukuPermission);
        });
        Shizuku.addBinderDeadListener(() -> {
            runOnUiThread(() -> emitShizukuStatus("not_running"));
        });
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    // ─────────────────────────────────────────────────────────
    // Diagnóstico Shizuku
    // ─────────────────────────────────────────────────────────
    private boolean isShizukuInstalled() {
        try {
            getPackageManager().getPackageInfo("moe.shizuku.privileged.api", 0);
            return true;
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }

    private JSONObject getShizukuDiagnostics() {
        JSONObject diag = new JSONObject();
        try {
            diag.put("isShizukuInstalled", isShizukuInstalled());
            diag.put("pingBinder", Shizuku.pingBinder());
            
            if (Shizuku.pingBinder()) {
                diag.put("isPreV11", Shizuku.isPreV11());
                diag.put("checkSelfPermission", Shizuku.checkSelfPermission()); // 0 = GRANTED, -1 = DENIED
                diag.put("shouldShowRationale", Shizuku.shouldShowRequestPermissionRationale());
            }
        } catch (Exception e) {
            try {
                diag.put("error", e.getMessage());
            } catch (Exception ignored) {}
        }
        return diag;
    }

    // ─────────────────────────────────────────────────────────
    // Shizuku Setup
    // ─────────────────────────────────────────────────────────
    private void checkShizukuPermission() {
        try {
            // 1º: O Binder está vivo? (O Shizuku está rodando?)
            if (!Shizuku.pingBinder()) {
                emitShizukuStatus("not_running");
                return;
            }
            // 2º: A versão é suportada?
            if (Shizuku.isPreV11()) {
                emitShizukuStatus("unsupported");
                return;
            }
            // 3º: A permissão foi concedida?
            if (Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) {
                emitShizukuStatus("granted");
            } else if (Shizuku.shouldShowRequestPermissionRationale()) {
                emitShizukuStatus("denied");
            } else {
                emitShizukuStatus("requesting");
                Shizuku.requestPermission(SHIZUKU_CODE);
            }
        } catch (Exception e) {
            // Se der qualquer erro (ex: Binder morto), consideramos como não rodando.
            emitShizukuStatus("not_running");
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == SHIZUKU_CODE) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                emitShizukuStatus("granted");
            } else {
                emitShizukuStatus("denied");
            }
        }
    }

    private void emitShizukuStatus(String status) {
        String js = "window.__dx_on_shizuku__ && window.__dx_on_shizuku__('" + status + "');";
        webView.post(() -> webView.evaluateJavascript(js, null));
    }

    // ─────────────────────────────────────────────────────────
    // Execução de shell via Shizuku (reflexão)
    // ─────────────────────────────────────────────────────────
    private Process executeShellCommand(String command) throws Exception {
        java.lang.reflect.Method method = Shizuku.class.getDeclaredMethod(
            "newProcess", String[].class, String[].class, String.class
        );
        method.setAccessible(true);
        return (Process) method.invoke(null, new String[]{"sh", "-c", command}, null, null);
    }

    // ─────────────────────────────────────────────────────────
    // Focus Stack (Tier 2 via Shizuku)
    // ─────────────────────────────────────────────────────────
    private JSONArray getFocusStack() {
        JSONArray stack = new JSONArray();
        try {
            Process process = executeShellCommand("dumpsys audio");
            BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));
            String line;
            boolean inFocus = false;
            JSONObject current = null;

            Pattern pPkg = Pattern.compile("pack[:\\s]+([a-zA-Z0-9_.]+)");
            Pattern pGain = Pattern.compile("gain[:\\s]+([A-Z_]+)");
            Pattern pState = Pattern.compile("state[:\\s]+([A-Z_]+)");

            while ((line = reader.readLine()) != null) {
                if (line.contains("Audio Focus stack entries") || line.contains("Audio Focus Stack")) {
                    inFocus = true;
                    continue;
                }
                if (inFocus) {
                    if (line.trim().isEmpty() && current != null) {
                        stack.put(current);
                        current = null;
                        continue;
                    }
                    Matcher mPkg = pPkg.matcher(line);
                    if (mPkg.find()) {
                        if (current != null) stack.put(current);
                        current = new JSONObject();
                        current.put("package", mPkg.group(1));
                    }
                    if (current != null) {
                        Matcher mGain = pGain.matcher(line);
                        if (mGain.find()) current.put("gain", mGain.group(1));
                        Matcher mState = pState.matcher(line);
                        if (mState.find()) current.put("state", mState.group(1));
                    }
                }
            }
            if (current != null) stack.put(current);
            reader.close();
        } catch (Exception e) {
            Log.e(TAG, "getFocusStack error: " + e.getMessage());
        }
        return stack;
    }

    // ─────────────────────────────────────────────────────────
    // Audio Snapshot (Tier 1 + 2)
    // ─────────────────────────────────────────────────────────
    private JSONObject buildAudioSnapshot() {
        JSONObject snap = new JSONObject();
        try {
            snap.put("timestamp", System.currentTimeMillis());
            snap.put("isMusicActive", audioManager.isMusicActive());
            snap.put("mode", audioManager.getMode());
            snap.put("ringerMode", audioManager.getRingerMode());

            JSONObject volumes = new JSONObject();
            int[] streams = {AudioManager.STREAM_MUSIC, AudioManager.STREAM_VOICE_CALL, AudioManager.STREAM_RING};
            String[] names = {"music", "voice_call", "ring"};
            for (int i = 0; i < streams.length; i++) {
                JSONObject s = new JSONObject();
                s.put("current", audioManager.getStreamVolume(streams[i]));
                s.put("max", audioManager.getStreamMaxVolume(streams[i]));
                volumes.put(names[i], s);
            }
            snap.put("volumes", volumes);

            // Adiciona a pilha de foco se o Shizuku estiver ativo
            if (Shizuku.pingBinder() && Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) {
                snap.put("focusStack", getFocusStack());
            } else {
                snap.put("focusStack", new JSONArray());
            }
            
            snap.put("device", Build.MODEL);
        } catch (Exception e) {
            Log.e(TAG, "buildAudioSnapshot error: " + e.getMessage());
        }
        return snap;
    }

    // ─────────────────────────────────────────────────────────
    // Monitor Loop
    // ─────────────────────────────────────────────────────────
    private void startMonitorLoop() {
        if (isMonitoring) return;
        isMonitoring = true;
        lastStateJson = "";
        monitorRunnable = new Runnable() {
            @Override
            public void run() {
                if (!isMonitoring) return;
                try {
                    JSONObject snap = buildAudioSnapshot();
                    final String json = snap.toString();
                    if (!json.equals(lastStateJson)) {
                        lastStateJson = json;
                        final String js = "window.__dx_receive__({"
                            + "\"id\":\"audio_monitor\","
                            + "\"status\":\"success\","
                            + "\"action\":\"audio.state\","
                            + "\"payload\":" + json
                            + "});";
                        webView.post(() -> webView.evaluateJavascript(js, null));
                    }
                } catch (Exception e) {
                    Log.e(TAG, "monitor loop error: " + e.getMessage());
                }
                monitorHandler.postDelayed(this, monitorIntervalMs);
            }
        };
        monitorHandler.post(monitorRunnable);
    }

    private void stopMonitorLoop() {
        isMonitoring = false;
        if (monitorHandler != null && monitorRunnable != null) {
            monitorHandler.removeCallbacks(monitorRunnable);
        }
    }

    public class HermesBridge {
        @JavascriptInterface
        public void send(String jsonStr) {
            try {
                JSONObject request = new JSONObject(jsonStr);
                final String reqId = request.optString("id", "unknown");
                final String action = request.optString("action", "unknown");

                if ("shizuku.diag".equals(action)) {
                    emitResponse(reqId, action, getShizukuDiagnostics().toString());
                    return;
                }

                if ("audio.start_monitor".equals(action)) {
                    monitorIntervalMs = request.optLong("interval", 2000);
                    startMonitorLoop();
                    emitResponse(reqId, action, "{\"monitoring\":true}");
                    return;
                }
                if ("audio.stop_monitor".equals(action)) {
                    stopMonitorLoop();
                    emitResponse(reqId, action, "{\"monitoring\":false}");
                    return;
                }
                if ("audio.snapshot".equals(action)) {
                    emitResponse(reqId, action, buildAudioSnapshot().toString());
                    return;
                }
                if ("shizuku.check".equals(action)) {
                    checkShizukuPermission();
                    emitResponse(reqId, action, "{\"checking\":true}");
                    return;
                }

                emitResponse(reqId, action, "{\"pong\":true}");
            } catch (Exception e) {
                Log.e(TAG, "HermesBridge.send error: " + e.getMessage());
            }
        }

        private void emitResponse(final String reqId, final String action, final String payloadJson) {
            webView.post(() -> {
                String js = "window.__dx_receive__({"
                    + "\"id\":\"" + reqId + "\","
                    + "\"status\":\"success\","
                    + "\"action\":\"" + action + "\","
                    + "\"payload\":" + payloadJson
                    + "});";
                webView.evaluateJavascript(js, null);
            });
        }
    }
}
