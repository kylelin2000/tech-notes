# 雲端服務對照：AWS / Azure / GCP

以 [AWS Request Path](aws/request-path.md) 中出現的服務為基準，列出 Azure 與 GCP 功能相近的服務。它們只是功能相近，計費、限制和行為不會完全一樣。

| 類別 | AWS | Azure | GCP |
| --- | --- | --- | --- |
| DNS | Route 53 | Azure DNS（流量導向用 Traffic Manager） | Cloud DNS |
| CDN | CloudFront | Azure Front Door / Azure CDN | Cloud CDN |
| L7 防護 | WAF | Azure WAF（掛在 Front Door 或 Application Gateway） | Cloud Armor |
| DDoS | Shield | Azure DDoS Protection | Cloud Armor（含 DDoS 防護） |
| 憑證 | ACM | Key Vault 憑證 / App Service 憑證 | Certificate Manager |
| API 入口 | API Gateway | API Management | API Gateway / Apigee |
| 使用者登入 | Cognito | Microsoft Entra External ID（原 Azure AD B2C） | Identity Platform |
| L7 負載平衡 | ALB | Application Gateway | Cloud Load Balancing（Application Load Balancer） |
| 對外 NAT | NAT Gateway | NAT Gateway | Cloud NAT |
| 虛擬網路 | VPC（含 Internet Gateway） | Virtual Network (VNet) | VPC |
| 私網連接 | VPC Link / VPC Endpoints | Private Link / Private Endpoint | Private Service Connect |
| 防火牆 | Security Group / NACL | Network Security Group (NSG) | VPC 防火牆規則 |
| 容器（免管 node） | ECS on Fargate | Container Apps | Cloud Run |
| Kubernetes | EKS | AKS | GKE |
| 虛擬機 | EC2 | Virtual Machines | Compute Engine |
| 自動擴縮 | Auto Scaling | VM Scale Sets | Managed Instance Groups |
| 免伺服器函式 | Lambda | Functions | Cloud Run functions |
| 快取 | ElastiCache Redis | Azure Cache for Redis / Managed Redis | Memorystore |
| 關聯式資料庫 | Aurora / RDS | Azure SQL Database / Database for PostgreSQL、MySQL | Cloud SQL / AlloyDB |
| 全文搜尋 | OpenSearch | Azure AI Search（或 Elastic on Azure） | 無直接對應（Elastic Cloud 或 Vertex AI Search） |
| NoSQL | DynamoDB | Cosmos DB | Firestore / Bigtable |
| 物件儲存 | S3 | Blob Storage | Cloud Storage |
| 佇列 | SQS | Storage Queues / Service Bus | Pub/Sub / Cloud Tasks |
| 發布訂閱 | SNS | Service Bus Topics / Event Grid | Pub/Sub |
| 事件路由 | EventBridge | Event Grid | Eventarc |
| 串流 | Kinesis | Event Hubs | Pub/Sub / Dataflow |
| 託管 Kafka | MSK | Event Hubs for Kafka | Managed Service for Apache Kafka |
| 權限身分 | IAM Role | Managed Identity + Azure RBAC | Service Account + IAM |
| 金鑰管理 | KMS | Key Vault | Cloud KMS |
| 機密管理 | Secrets Manager | Key Vault | Secret Manager |
| 威脅偵測 | GuardDuty | Defender for Cloud | Security Command Center |
| 稽核紀錄 | CloudTrail | Activity Log | Cloud Audit Logs |
| 設定合規 | AWS Config | Azure Policy | Cloud Asset Inventory |
| 監控與日誌 | CloudWatch | Azure Monitor | Cloud Monitoring / Logging |
| 分散式追蹤 | X-Ray | Application Insights | Cloud Trace |
| 映像倉庫 | ECR | Container Registry (ACR) | Artifact Registry |
| CI/CD | CodePipeline | Azure Pipelines | Cloud Build / Cloud Deploy |
| 主機管理 | Systems Manager | Azure Automation / Update Manager | VM Manager |

差異比較大的幾組：OpenSearch 在 GCP 沒有第一方對應，Aurora 在 GCP 最接近的是 AlloyDB，DynamoDB 在 Azure 和 GCP 都沒有一對一的產品。
