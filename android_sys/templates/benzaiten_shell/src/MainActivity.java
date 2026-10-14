package com.doxoade.benzaiten;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import android.util.Log;

public class MainActivity extends Activity {
    private WebView webView;
    private static final String TAG = "BenzaitenMobile";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);

        webView.addJavascriptInterface(new HermesBridge(), "__dx_native__");
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.loadUrl("file:///android_asset/index.html");
        setContentView(webView);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    public class HermesBridge {
        @JavascriptInterface
        public void send(String payload) {
            Log.d(TAG, "Hermes Message Received: " + payload);
            webView.post(new Runnable() {
                @Override
                public void run() {
                    String echo = "{\"status\":\"success\",\"payload\":{\"pong\":true}}";
                    webView.evaluateJavascript("window.__dx_receive__('" + echo + "');", null);
                }
            });
        }
    }
}
