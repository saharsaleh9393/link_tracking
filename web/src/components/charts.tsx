"use client";
import { useLocale, useTranslations } from "next-intl";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Empty } from "./shared";
export function Chart({
  title,
  points,
  area = false,
}: {
  title: string;
  points: { label: string; value: number }[];
  area?: boolean;
}) {
  const locale = useLocale(),
    t = useTranslations();
  const format = (value: number) =>
    new Intl.NumberFormat(locale, { notation: "compact" }).format(value);
  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {!points.length ? (
          <Empty hint={t("noData")} />
        ) : (
          <div className="h-72 w-full" dir="ltr">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              {area ? (
                <AreaChart
                  data={points}
                  margin={{ left: 0, right: 20, top: 15, bottom: 0 }}
                >
                  <defs>
                    <linearGradient
                      id="activityFill"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop offset="0%" stopColor="#7566e7" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="#7566e7" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="4 4"
                    vertical={false}
                    stroke="#edf0f5"
                  />
                  <XAxis
                    dataKey="label"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 11, fill: "#8b94a8" }}
                    minTickGap={35}
                  />
                  <YAxis
                    tickFormatter={format}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 11, fill: "#8b94a8" }}
                    width={45}
                  />
                  <Tooltip
                    formatter={(value) => [
                      new Intl.NumberFormat(locale).format(Number(value)),
                      t("clickCount"),
                    ]}
                    contentStyle={{
                      borderRadius: 12,
                      border: "1px solid #e8ebf1",
                      fontSize: 12,
                    }}
                  />
                  <Area
                    name={t("clickCount")}
                    type="monotone"
                    dataKey="value"
                    stroke="#7566e7"
                    strokeWidth={3}
                    fill="url(#activityFill)"
                    dot={{ r: 3, strokeWidth: 2, fill: "white" }}
                    activeDot={{ r: 5 }}
                    isAnimationActive={false}
                  />
                </AreaChart>
              ) : (
                <BarChart
                  data={points}
                  margin={{ left: 0, right: 10, top: 15, bottom: 10 }}
                >
                  <CartesianGrid vertical={false} stroke="#edf0f5" />
                  <XAxis
                    dataKey="label"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 10, fill: "#8b94a8" }}
                    minTickGap={10}
                  />
                  <YAxis
                    tickFormatter={format}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 11, fill: "#8b94a8" }}
                    width={45}
                  />
                  <Tooltip
                    formatter={(value) => [
                      new Intl.NumberFormat(locale).format(Number(value)),
                      t("clickCount"),
                    ]}
                    contentStyle={{
                      borderRadius: 12,
                      border: "1px solid #e8ebf1",
                      fontSize: 12,
                    }}
                  />
                  <Bar
                    name={t("clickCount")}
                    dataKey="value"
                    fill="#8274e9"
                    radius={[5, 5, 0, 0]}
                    maxBarSize={48}
                    isAnimationActive={false}
                  />
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
