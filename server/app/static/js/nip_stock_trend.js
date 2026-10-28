(() => {
    const el = id => document.getElementById(id), controls = {};
    let applied = new URLSearchParams(), chart = null, data = null, pending = null, mode = 'graph', tablePage = 1;
    const headers = () => ({Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`});
    const name = key => key.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
    const number = value => value == null ? 'N/A' : Number(value).toLocaleString('en-IN', {
        minimumFractionDigits: data?.metric === 'pieces' ? 0 : 3, maximumFractionDigits: data?.metric === 'pieces' ? 0 : 3});
    async function responseJSON(response) {
        const value = await response.json();
        if (!response.ok) throw new Error(value.error || value.msg || 'Unable to load report');
        return value;
    }
    function collect() {
        const params = new URLSearchParams();
        for (const [field, control] of Object.entries(controls)) for (const value of control.getValues()) params.append(field, value);
        for (const [key, id] of [['from_date','nip-from'],['to_date','nip-to']]) if (el(id).value) params.set(key, el(id).value);
        document.querySelectorAll('[data-nip-boolean]').forEach(node => {if (node.value) params.set(node.dataset.nipBoolean, node.value);});
        return params;
    }
    function requestParams() {
        const params = new URLSearchParams(applied);
        for (const [key,id] of [['metric','nip-metric'],['group_by','nip-group'],['interval','nip-interval']]) params.set(key, el(id).value);
        return params;
    }
    function showViews() {
        el('nip-graph').hidden = mode === 'table'; el('nip-table').hidden = mode === 'graph';
        document.querySelectorAll('[data-view]').forEach(node => node.setAttribute('aria-pressed', String(node.dataset.view === mode)));
        chart?.resize();
    }
    function draw() {
        chart?.destroy(); chart = null;
        if (!data) return;
        const datasets = [];
        data.series.forEach((series, i) => {
            if (i && series.group !== data.series[i-1].group) datasets.push({
                type:'bar',label:'',data:data.periods.map(()=>null),groupSpacer:true,order:1
            });
            const color = ({total:'#1683ef',nip:'#e59b18',excess:'#e05260'})[series.kind] || `hsl(${(i * 137.508) % 360} 65% 44%)`;
            datasets.push({type:'bar',label:series.name,stockKind:series.kind,comparisonGroup:series.group,data:series.values,borderColor:color,backgroundColor:color,
                borderWidth:1,barPercentage:0.96,order:1});
            if (el('nip-average').checked) datasets.push({type:'line',label:`${series.name} (3-period MA)`,stockKind:series.kind,comparisonGroup:series.group,borderColor:color,
                backgroundColor:color,order:0,
                borderDash:[5,4],pointRadius:0,borderWidth:1,spanGaps:false,
                data:series.values.map((_,index) => index < 2 || series.values.slice(index-2,index+1).some(v=>v==null)
                    ? null : series.values.slice(index-2,index+1).reduce((sum,v)=>sum+v,0)/3)});
        });
        if (typeof Chart !== 'undefined') {
            Chart.Interaction.modes.nipGroup=(current,event,options,useFinalPosition)=>{
                const nearest=current.getElementsAtEventForMode(event,'nearest',{axis:'xy',intersect:false},useFinalPosition)[0];
                if(!nearest)return [];
                const group=current.data.datasets[nearest.datasetIndex].comparisonGroup;
                return current.data.datasets.flatMap((dataset,index)=>{
                    if(dataset.type!=='bar'||dataset.groupSpacer||dataset.comparisonGroup!==group||!current.isDatasetVisible(index)
                        ||dataset.data[nearest.index]==null)return [];
                    return [{element:current.getDatasetMeta(index).data[nearest.index],datasetIndex:index,index:nearest.index}];
                });
            };
            chart = new Chart(el('nip-chart'), {type:'bar',data:{labels:data.periods,datasets},plugins:[{
            id:'categoryGroupSpacing',
            beforeDatasetsUpdate(current) {
                const bars=current.data.datasets.filter(dataset=>dataset.type==='bar');
                const visibleBars=bars.filter(dataset=>current.isDatasetVisible(current.data.datasets.indexOf(dataset)));
                // Reserve one empty bar slot between comparison groups, keeping each trio tight.
                const slot=Math.min(29,current.chartArea.width/Math.max(1,data.periods.length)/Math.max(1,visibleBars.length)*0.8);
                const categoryWidth=slot*visibleBars.length;
                bars.forEach(dataset=>{
                    dataset.categoryPercentage=categoryWidth/(current.chartArea.width/Math.max(1,data.periods.length));
                    dataset.maxBarThickness=slot;
                });
            },
            afterDatasetsUpdate(current) {
                current.data.datasets.forEach((dataset,index)=>{
                    if(dataset.type!=='bar'||dataset.groupSpacer)return;
                    current.getDatasetMeta(index).data.forEach((bar,position)=>{
                        const value=dataset.data[position];
                        if(value==null||Number(value)===0)return;
                        const target=bar.getProps(['y','base'],true);
                        if(Math.abs(target.base-target.y)<3){
                            const y=target.base+(Number(value)>0?-3:3);
                            bar.y=y;
                            bar.height=3;
                        }
                    });
                });
            },
            afterDraw(current) {
                const groups=new Map();
                current.data.datasets.forEach((dataset,index)=>{
                    if(dataset.type!=='bar'||dataset.groupSpacer||!current.isDatasetVisible(index))return;
                    if(!groups.has(dataset.comparisonGroup))groups.set(dataset.comparisonGroup,[]);
                    groups.get(dataset.comparisonGroup).push(current.getDatasetMeta(index));
                });
                const ctx=current.ctx;
                ctx.save();ctx.font='500 11px sans-serif';ctx.textAlign='center';ctx.textBaseline='top';
                ctx.fillStyle=document.documentElement.classList.contains('dark')?'#d1d5db':'#4b5563';
                data.periods.forEach((_,position)=>{
                    groups.forEach((metas,group)=>{
                        const bars=metas.map(meta=>meta.data[position]).filter(Boolean);
                        if(!bars.length)return;
                        const left=Math.min(...bars.map(bar=>bar.x-bar.width/2));
                        const right=Math.max(...bars.map(bar=>bar.x+bar.width/2));
                        const label=data.group_by==='purity'&&Number.isFinite(Number(group))?String(Number(group)):String(group);
                        ctx.fillText(label,(left+right)/2,current.chartArea.bottom+7,Math.max(1,right-left));
                    });
                });
                ctx.restore();
                ctx.save();
                ctx.font='500 10px sans-serif';ctx.textAlign='left';ctx.textBaseline='middle';
                ctx.fillStyle=document.documentElement.classList.contains('dark')?'#e5e7eb':'#374151';
                current.data.datasets.forEach((dataset,index)=>{
                    if(dataset.type!=='bar'||dataset.groupSpacer||!current.isDatasetVisible(index))return;
                    current.getDatasetMeta(index).data.forEach((bar,position)=>{
                        const value=dataset.data[position];
                        if(value==null)return;
                        ctx.save();
                        ctx.translate(bar.x,Math.min(bar.y,bar.base)-5);
                        ctx.rotate(-Math.PI/2);
                        ctx.fillText(number(value),0,0);
                        ctx.restore();
                    });
                });
                ctx.restore();
            }
        }],options:{
            responsive:true,maintainAspectRatio:false,animation:false,layout:{padding:{top:70}},interaction:{mode:'nipGroup',intersect:false},
            scales:{x:{ticks:{padding:26}},y:{beginAtZero:true,title:{display:true,text:data.unit},ticks:{precision:data.metric==='pieces'?0:3}}},
            plugins:{legend:{position:'bottom',labels:{generateLabels:current=>[
                ['total','Total Stock'],['nip','NIP Stock'],['excess','Excess Stock']
            ].flatMap(([kind,label])=>{
                const index=current.data.datasets.findIndex(dataset=>dataset.type==='bar'&&dataset.stockKind===kind);
                if(index<0)return [];
                const dataset=current.data.datasets[index];
                return [{text:label,fillStyle:dataset.backgroundColor,strokeStyle:dataset.borderColor,lineWidth:1,
                    hidden:!current.data.datasets.some((item,i)=>item.type==='bar'&&item.stockKind===kind&&current.isDatasetVisible(i)),
                    datasetIndex:index,stockKind:kind}];
            })},onClick:(_,item,legend)=>{
                const current=legend.chart;
                const visible=!current.data.datasets.some((dataset,index)=>dataset.type==='bar'&&dataset.stockKind===item.stockKind&&current.isDatasetVisible(index));
                current.data.datasets.forEach((dataset,index)=>{
                    if(dataset.stockKind===item.stockKind)current.setDatasetVisibility(index,visible);
                });
                current.update();
            }},tooltip:{filter:item=>!item.dataset.groupSpacer,callbacks:{title:items => `${items[0].label} (balance ${data.balance_dates[items[0].dataIndex]})`,
                label:context=>`${context.dataset.label}: ${number(context.raw)} ${data.unit}`}}}}});
        } else el('nip-status').textContent += ' Chart library unavailable; table values remain available.';
    }
    function renderTable() {
        el('nip-table').replaceChildren();
        const table = document.createElement('table'), head = table.createTHead().insertRow();
        for (const text of ['Time Period','Balance Date',name(data.group_by),`Total (${data.unit})`,`NIP (${data.unit})`,`Excess (${data.unit})`]) {
            const th=document.createElement('th');th.textContent=text;head.append(th);
        }
        const body=table.createTBody();
        const rows=data.table_rows || [],total=rows.length, start=(tablePage-1)*50;
        for(let index=start;index<Math.min(total,start+50);index++){
            const record=rows[index],row=body.insertRow();
            for(const value of [record.period,record.balance_date,record.group,number(record.total),number(record.nip),number(record.excess)]) row.insertCell().textContent=value;
        }
        const scroll=document.createElement('div');scroll.className='nip-table-scroll';scroll.append(table);
        el('nip-table').append(scroll);
        const paging=document.createElement('div');paging.className='flex items-center justify-end gap-3 px-4 py-2 text-xs';
        const label=document.createElement('span');label.textContent=`${total?start+1:0}-${Math.min(total,start+50)} of ${total}`;paging.append(label);
        for(const [direction,icon] of [[-1,'chevron_left'],[1,'chevron_right']]){
            const button=document.createElement('button');button.className='nip-icon';button.title=direction<0?'Previous page':'Next page';button.setAttribute('aria-label',button.title);
            const symbol=document.createElement('span');symbol.className='material-symbols-outlined';symbol.textContent=icon;button.append(symbol);
            button.disabled=direction<0?tablePage===1:start+50>=total;button.onclick=()=>{tablePage+=direction;renderTable();};paging.append(button);
        }
        el('nip-table').append(paging);
    }
    function render() {
        for (const key of ['opening','closing','change','change_pct','average']) {
            el(`nip-stat-${key}`).textContent = key === 'change_pct'
                ? (data.stats[key] == null ? 'N/A' : data.stats[key].toFixed(2)+'%') : number(data.stats[key]);
        }
        document.querySelectorAll('.nip-unit').forEach((node,i)=>node.textContent=i===3?'':data.unit);
        tablePage=1;renderTable();
        el('nip-status').textContent = data.periods.length
            ? `${data.first_date} to ${data.last_date} · ${data.observed_days} observed days · Total / NIP / Excess · ${data.interval === 'daily' ? 'Daily balances' : 'Last reporting date per period'}${data.missing_measure_rows ? ' · Missing measurements: '+data.missing_measure_rows : ''}`
            : 'No stock balances match these filters. Run the sync in Settings or change the selected dates.';
        draw(); showViews();
    }
    async function load() {
        pending?.abort(); const controller=new AbortController();pending=controller;
        el('nip-status').textContent='Loading stock history...';
        try {
            const result=await responseJSON(await fetch('/api/nip-stock-trend-analysis/data?'+requestParams(), {headers:headers(),signal:controller.signal}));
            if(controller.signal.aborted)return;
            data=result;render();
        } catch(error){if(error.name!=='AbortError'){el('nip-status').textContent=error.message;data=null;chart?.destroy();chart=null;el('nip-table').replaceChildren();
            ['opening','closing','change','change_pct','average'].forEach(key=>el('nip-stat-'+key).textContent='-');}}
    }
    async function download(response,filename) {
        if(!response.ok)throw new Error((await response.json()).error || 'Export permission required');
        const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    document.addEventListener('DOMContentLoaded', async()=>{
        el('nip-apply').onclick=()=>{applied=collect();load();};
        const clear=()=>{Object.values(controls).forEach(control=>control.reset());el('nip-from').value='';el('nip-to').value='';
            document.querySelectorAll('[data-nip-boolean]').forEach(node=>node.value='');applied=new URLSearchParams();load();};
        el('nip-clear').onclick=clear;el('nip-reset').onclick=clear;el('nip-refresh').onclick=load;
        ['nip-interval','nip-metric','nip-group'].forEach(id=>el(id).onchange=load);el('nip-average').onchange=draw;
        document.querySelectorAll('[data-view]').forEach(node=>node.onclick=()=>{mode=node.dataset.view;showViews();});
        el('nip-filter-toggle').onclick=()=>{const node=el('nip-sidebar');node.hidden=!node.hidden;node.style.display=node.hidden?'none':'';
            el('nip-filter-toggle').setAttribute('aria-expanded',String(!node.hidden));chart?.resize();};
        el('nip-expand').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await el('nip-graph').requestFullscreen();}catch{el('nip-status').textContent='Fullscreen is unavailable in this browser.';}};
        document.addEventListener('fullscreenchange',()=>{const expanded=!!document.fullscreenElement;
            el('nip-expand').title=expanded?'Exit expanded graph':'Expand graph';
            el('nip-expand').setAttribute('aria-label',el('nip-expand').title);
            el('nip-expand').querySelector('span').textContent=expanded?'fullscreen_exit':'fullscreen';chart?.resize();});
        el('nip-png').onclick=()=>{if(!chart||!data?.periods.length)return;const a=document.createElement('a');a.href=chart.toBase64Image();a.download='nip-stock-trend.png';a.click();};
        if(el('nip-export'))el('nip-export').onclick=async()=>{const button=el('nip-export');button.disabled=true;try{await download(await fetch('/api/nip-stock-trend-analysis/export?'+requestParams(),{headers:headers()}),'nip_stock_trend.xlsx');}
            catch(error){el('nip-status').textContent=error.message;}finally{button.disabled=false;}};
        try {
            const result=await responseJSON(await fetch('/api/nip-stock-trend-analysis/options',{headers:headers()}));
            for(const [key,values] of Object.entries(result.options))controls[key]=new CustomMultiSelect({containerId:'nip-filter-'+key,label:name(key),defaultText:'All '+name(key),options:values.map(value=>({value,label:value}))});
            await load();
        }catch(error){el('nip-status').textContent=error.message;}
    });
})();
