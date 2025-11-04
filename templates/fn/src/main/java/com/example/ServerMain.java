package com.example;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;

public final class ServerMain {
    private static final AtomicLong REQUESTS = new AtomicLong();

    public static void main(String[] args) throws Exception {
        int port = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));
        Path profilePath = Path.of(System.getenv().getOrDefault("PROFILE_PATH", "/profiles/latest.mdox"));
        Path dumpPath = Path.of(System.getenv().getOrDefault("PROFILE_DUMP_PATH", "/profiles/out.mdox"));

        GeorgeProfile.loadIfPresent(profilePath);

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("JVM_SHUTDOWN_HOOK_START");
            GeorgeProfile.dumpBestEffort(dumpPath);
            System.out.println("JVM_SHUTDOWN_HOOK_DONE");
        }));

        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/", ServerMain::handle);
        server.setExecutor(Executors.newFixedThreadPool(4));
        server.start();
        System.out.println("SERVER_READY port=" + port);
    }

    private static void handle(HttpExchange exchange) throws IOException {
        long n = REQUESTS.incrementAndGet();
        Map<String, String> q = parseQuery(exchange.getRequestURI());
        String name = q.getOrDefault("name", "world");

        // Small hot loop so repeated invocations create profile data.
        long acc = 0;
        for (int i = 0; i < 200_000; i++) {
            acc += ((i * 31L) ^ name.hashCode()) & 0xff;
        }

        String body = "{\"ok\":true,\"request\":" + n + ",\"name\":\"" + escape(name) + "\",\"acc\":" + acc + "}";
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, bytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }

    private static Map<String, String> parseQuery(URI uri) {
        Map<String, String> out = new HashMap<>();
        String raw = uri.getRawQuery();
        if (raw == null || raw.isEmpty()) return out;
        for (String part : raw.split("&")) {
            String[] kv = part.split("=", 2);
            String k = decode(kv[0]);
            String v = kv.length > 1 ? decode(kv[1]) : "";
            out.put(k, v);
        }
        return out;
    }

    private static String decode(String s) {
        return s.replace("+", " ");
    }

    private static String escape(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
