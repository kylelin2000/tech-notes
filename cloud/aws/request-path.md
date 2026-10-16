# AWS Request Path

一個 HTTPS 請求從瀏覽器進來，到資料落地、非同步處理為止，常見會經過的 AWS 服務與它們之間的關係。

![AWS Request Path](assets/request-path.svg)

實線是使用者在等的同步請求，虛線是丟進 queue 之後由 worker 回頭消費的路徑。VPC 內分 public、應用、資料三層 subnet，只有 ALB 與 NAT 在 public subnet。

## 每一跳在做什麼

1. **DNS。** Route 53 把網域 alias 到 CloudFront，也可以在多個 region 之間做健康檢查與 failover。
2. **HTTPS。** 瀏覽器連到最近的 CloudFront edge，TLS 用 ACM 憑證終止，WAF 與 Shield 在這裡擋掉惡意請求。靜態內容直接由快取或 S3 回應。
3. **回源。** 動態請求走預設 origin 到 ALB，或把 `/api/*` 導向 API Gateway。API Gateway 用 Cognito 的 JWT 驗證與限流，再經 VPC Link 進 VPC。
4. **轉發。** ALB 依 path 或 host 送到 target group，target 可以是 ECS、EKS、EC2 或 Lambda，並持續做 health check。
5. **讀寫資料。** 應用先查 Redis，miss 才讀 Aurora 或 RDS。搜尋走 OpenSearch。DynamoDB、S3、SQS 透過 VPC Endpoint 走私網，不經 NAT。
6. **非同步。** 寄信、轉檔、扣庫存這類工作丟進 SQS、SNS、EventBridge 或 Kinesis，由 worker 消費。只有呼叫第三方 API 時才經過 NAT Gateway。

## 三個要做的選擇

| 決定 | 選項與判斷 |
| --- | --- |
| 運算 | 流量不穩或事件驅動選 Lambda。跑容器又不想管 node 選 ECS on Fargate。已有 Kubernetes 生態或需要細緻排程選 EKS。需要特殊 OS、GPU 或長駐程序才選 EC2。 |
| 入口 | ALB 適合容器與長連線服務。API Gateway 適合需要 authorizer、usage plan、stage 管理的 API，兩者計費方式不同，ALB 依時間與用量，API Gateway 依請求數。 |
| 資料 | 需要 join 與交易選 Aurora 或 RDS。access pattern 已知且吞吐很高選 DynamoDB。Redis 是加速層，不當作唯一的資料來源。 |

## 橫切關注點

- 安全：IAM Role、KMS、Secrets Manager、Security Group / NACL、GuardDuty、CloudTrail、AWS Config
- 營運：CloudWatch、X-Ray、ECR、CodePipeline、Systems Manager、Auto Scaling

---

其他雲端的對應服務請見 [雲端服務對照：AWS / Azure / GCP](../service-mapping.md)。
