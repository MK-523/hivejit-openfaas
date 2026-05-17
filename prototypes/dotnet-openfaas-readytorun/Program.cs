using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Http.Json;

var builder = WebApplication.CreateSlimBuilder(args);
builder.WebHost.UseUrls(Environment.GetEnvironmentVariable("HANDLER_ADDR") ?? "http://0.0.0.0:8082");
builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.TypeInfoResolverChain.Insert(0, AppJsonSerializerContext.Default);
    options.SerializerOptions.PropertyNameCaseInsensitive = true;
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
});

var app = builder.Build();
app.MapGet("/healthz", () => Results.Json(
    new HealthResponse(true, BuildLabel()),
    AppJsonSerializerContext.Default.HealthResponse));
app.MapPost("/", (WorkRequest request) => RunWork(request));
app.MapPost("/work", (WorkRequest request) => RunWork(request));
app.MapGet("/", (HttpRequest request) => RunWork(WorkRequest.FromQuery(request)));
app.MapGet("/work", (HttpRequest request) => RunWork(WorkRequest.FromQuery(request)));
app.Run();

static IResult RunWork(WorkRequest request)
{
    long requestInPod = RuntimeState.NextRequestNumber();
    string scenario = string.IsNullOrWhiteSpace(request.Scenario) ? "serve-hot" : request.Scenario;
    int invocations = request.Invocations.GetValueOrDefault(1);
    ulong iterations = request.Iterations ?? request.Requests ?? 250_000UL;
    ulong seed = request.Seed ?? (ulong)DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

    if (invocations <= 0 || iterations == 0)
    {
        return Results.Json(
            new ErrorResponse("invocations and iterations must be positive"),
            AppJsonSerializerContext.Default.ErrorResponse,
            statusCode: StatusCodes.Status400BadRequest);
    }

    Result result = Workload.Run(scenario, invocations, iterations, seed);
    return Results.Json(
        new WorkResponse(
            result.Scenario,
            result.Invocations,
            result.IterationsPerInvoke,
            result.ElapsedMs,
            result.InvocationP50Ms,
            result.InvocationP95Ms,
            result.Checksum.ToString("x16"),
            result.Runtime,
            result.OSArchitecture,
            BuildLabel(),
            Environment.MachineName,
            Environment.GetEnvironmentVariable("POD_UID") ?? Environment.MachineName,
            RuntimeState.ProcessUptimeMs(),
            requestInPod,
            Environment.ProcessId),
        AppJsonSerializerContext.Default.WorkResponse);
}

static string BuildLabel()
{
    string path = "/app/build-label";
    if (File.Exists(path))
    {
        return File.ReadAllText(path).Trim();
    }
    return Environment.GetEnvironmentVariable("BUILD_LABEL") ?? "unknown";
}

sealed record WorkRequest(string? Scenario, int? Invocations, ulong? Iterations, ulong? Requests, ulong? Seed)
{
    public static WorkRequest FromQuery(HttpRequest request)
    {
        IQueryCollection query = request.Query;
        return new WorkRequest(
            Scenario: query.TryGetValue("scenario", out var scenario) ? scenario.ToString() : null,
            Invocations: TryInt(query, "invocations"),
            Iterations: TryUlong(query, "iterations"),
            Requests: TryUlong(query, "requests"),
            Seed: TryUlong(query, "seed"));
    }

    private static int? TryInt(IQueryCollection query, string key)
    {
        return query.TryGetValue(key, out var value) && int.TryParse(value, out int parsed) ? parsed : null;
    }

    private static ulong? TryUlong(IQueryCollection query, string key)
    {
        return query.TryGetValue(key, out var value) && ulong.TryParse(value, out ulong parsed) ? parsed : null;
    }
}

sealed record HealthResponse(bool Ok, string Build);

sealed record ErrorResponse(string Error);

sealed record WorkResponse(
    string Scenario,
    int Invocations,
    ulong IterationsPerInvoke,
    double ElapsedMs,
    double P50Ms,
    double P95Ms,
    string Checksum,
    string Runtime,
    string OSArchitecture,
    string Build,
    string Hostname,
    string PodUid,
    double ProcessUptimeMs,
    long RequestInPod,
    int ProcessId);

[JsonSourceGenerationOptions(PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
[JsonSerializable(typeof(WorkRequest))]
[JsonSerializable(typeof(HealthResponse))]
[JsonSerializable(typeof(ErrorResponse))]
[JsonSerializable(typeof(WorkResponse))]
internal sealed partial class AppJsonSerializerContext : JsonSerializerContext;

static class RuntimeState
{
    private static readonly Stopwatch Uptime = Stopwatch.StartNew();
    private static long RequestCount;

    public static long NextRequestNumber()
    {
        return Interlocked.Increment(ref RequestCount);
    }

    public static double ProcessUptimeMs()
    {
        return Uptime.Elapsed.TotalMilliseconds;
    }
}

interface IRoute
{
    ulong Run(ulong value);
}

sealed class HotRoute : IRoute
{
    public ulong Run(ulong value)
    {
        unchecked
        {
            for (ulong i = 0; i < 9; i++)
            {
                value = Workload.Mix64(value + i * 0x9e3779b97f4a7c15UL);
            }
            return value;
        }
    }
}

sealed class ParseRoute : IRoute
{
    public ulong Run(ulong value)
    {
        unchecked
        {
            for (ulong i = 0; i < 15; i++)
            {
                value = (value << 7) ^ (value >> 3) ^ Workload.Mix64(value + i);
            }
            return value;
        }
    }
}

sealed class RegexRoute : IRoute
{
    public ulong Run(ulong value)
    {
        unchecked
        {
            for (ulong i = 0; i < 19; i++)
            {
                value ^= (value & 1UL) == 0 ? Workload.Mix64(value + 31) : Workload.Mix64(value + 17);
            }
            return value;
        }
    }
}

sealed class GraphRoute : IRoute
{
    public ulong Run(ulong value)
    {
        unchecked
        {
            for (ulong i = 0; i < 23; i++)
            {
                value += Workload.Mix64(value ^ (i * 0x100000001b3UL));
            }
            return value;
        }
    }
}

sealed record Result(
    string Domain,
    string Scenario,
    DateTimeOffset GeneratedAt,
    string Runtime,
    string OSArchitecture,
    int Invocations,
    ulong IterationsPerInvoke,
    double ElapsedMs,
    double PerInvocationNs,
    IReadOnlyList<double> InvocationTimesMs,
    double InvocationP50Ms,
    double InvocationP95Ms,
    ulong Checksum);

static class Workload
{
    private static readonly IRoute[] Routes =
    [
        new HotRoute(),
        new ParseRoute(),
        new RegexRoute(),
        new GraphRoute(),
    ];

    public static ulong Mix64(ulong value)
    {
        unchecked
        {
            value ^= value >> 33;
            value *= 0xff51afd7ed558ccdUL;
            value ^= value >> 33;
            value *= 0xc4ceb9fe1a85ec53UL;
            value ^= value >> 33;
            return value;
        }
    }

    public static Result Run(string scenario, int invocations, ulong iterations, ulong seedBase)
    {
        List<double> invocationTimes = new(invocations);
        ulong checksum = 0UL;
        Stopwatch total = Stopwatch.StartNew();

        for (int i = 0; i < invocations; i++)
        {
            Stopwatch one = Stopwatch.StartNew();
            ulong seed = seedBase + ((ulong)i * 0x9e3779b97f4a7c15UL);
            checksum ^= InvokeHandler(scenario, iterations, seed);
            one.Stop();
            invocationTimes.Add(one.Elapsed.TotalMilliseconds);
        }

        total.Stop();
        return new Result(
            Domain: "dotnet-openfaas-readytorun",
            Scenario: scenario,
            GeneratedAt: DateTimeOffset.UtcNow,
            Runtime: Environment.Version.ToString(),
            OSArchitecture: RuntimeInformation.OSArchitecture.ToString(),
            Invocations: invocations,
            IterationsPerInvoke: iterations,
            ElapsedMs: total.Elapsed.TotalMilliseconds,
            PerInvocationNs: total.Elapsed.TotalMilliseconds * 1_000_000.0 / invocations / iterations,
            InvocationTimesMs: invocationTimes,
            InvocationP50Ms: Percentile(invocationTimes, 50),
            InvocationP95Ms: Percentile(invocationTimes, 95),
            Checksum: checksum);
    }

    private static int ChooseRoute(string scenario, ulong index, ulong state)
    {
        ulong ticket = Mix64(index ^ state) % 100UL;
        return scenario switch
        {
            "train" or "serve-hot" when ticket < 88 => 0,
            "train" or "serve-hot" when ticket < 94 => 1,
            "train" or "serve-hot" when ticket < 98 => 2,
            "train" or "serve-hot" => 3,
            "serve-mixed" when ticket < 45 => 0,
            "serve-mixed" when ticket < 65 => 1,
            "serve-mixed" when ticket < 84 => 2,
            "serve-mixed" => 3,
            _ => (int)(ticket & 3UL),
        };
    }

    private static ulong InvokeHandler(string scenario, ulong iterations, ulong seed)
    {
        unchecked
        {
            ulong state = seed;
            for (ulong i = 0; i < iterations; i++)
            {
                IRoute route = Routes[ChooseRoute(scenario, i, state)];
                state ^= route.Run(state + i);
            }
            return state;
        }
    }

    private static double Percentile(List<double> values, int percentile)
    {
        if (values.Count == 0)
        {
            return 0;
        }

        values.Sort();
        int index = (int)Math.Floor(percentile / 100.0 * values.Count);
        return values[Math.Min(index, values.Count - 1)];
    }
}
