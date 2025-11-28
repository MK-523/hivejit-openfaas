import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpExchange;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public class S {
  static byte[] slurp(InputStream in) throws Exception {
    ByteArrayOutputStream out = new ByteArrayOutputStream();
    byte[] buf = new byte[8192];
    int n;
    while ((n = in.read(buf)) != -1) out.write(buf, 0, n);
    return out.toByteArray();
  }

  static void send(HttpExchange e, int code, byte[] body) throws Exception {
    e.getResponseHeaders().set("Content-Type", "text/plain; charset=utf-8");
    e.sendResponseHeaders(code, body.length);
    try (OutputStream os = e.getResponseBody()) {
      os.write(body);
    }
  }

  public static void main(String[] args) throws Exception {
    HttpServer s = HttpServer.create(new InetSocketAddress(8080), 0);

    s.createContext("/_/health", e -> {
      try {
        send(e, 200, "OK".getBytes(StandardCharsets.UTF_8));
      } catch (Exception ex) {
        throw new RuntimeException(ex);
      }
    });

    s.createContext("/", e -> {
      try {
        long t0 = System.nanoTime();
        List<String> cmd = new ArrayList<>();
        cmd.add("/opt/george-jdk/bin/java");
        cmd.add("-jar");
        cmd.add("/app/lib/dacapo.jar");
        cmd.add("--data-set-location");
        cmd.add("/app/lib/dacapo");
        cmd.add("lusearch");
        cmd.add("-n");
        cmd.add("1");
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.redirectErrorStream(true);
        Process p = pb.start();
        byte[] out = slurp(p.getInputStream());
        int rc = p.waitFor();
        long ms = (System.nanoTime() - t0) / 1_000_000L;
        String body = "exit=" + rc + "\nelapsed_ms=" + ms + "\n" + new String(out, StandardCharsets.UTF_8);
        send(e, rc == 0 ? 200 : 500, body.getBytes(StandardCharsets.UTF_8));
      } catch (Exception ex) {
        String body = ex.toString() + "\n";
        try {
          send(e, 500, body.getBytes(StandardCharsets.UTF_8));
        } catch (Exception ex2) {
          throw new RuntimeException(ex2);
        }
      }
    });

    s.setExecutor(null);
    System.out.println("SERVER_READY port=8080");
    s.start();
  }
}
